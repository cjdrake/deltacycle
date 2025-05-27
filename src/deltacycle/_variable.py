"""Model variables"""

from __future__ import annotations

from abc import ABC
from collections import defaultdict
from collections.abc import Awaitable, Generator, Hashable
from typing import Any

from ._loop_if import LoopIf
from ._task import Predicate, Task, WaitTouch


class Variable(Awaitable[Any], LoopIf):
    """Model component.

    Children::

               Variable
                  |
           +------+------+
           |             |
        Singular     Aggregate
    """

    def __init__(self):
        self._waiting = WaitTouch()

    def __await__(self) -> Generator[None, Variable, Any]:
        task = self._loop.task()
        self._waiting.push((self.changed, task))
        v: Variable = yield from self._loop.switch_gen()
        assert v is self
        return v

    def _wait(self, p: Predicate, task: Task):
        self._waiting.push((p, task))

    def _set(self):
        self._waiting.touch()

        while self._waiting:
            task = self._waiting.pop()
            task._renege()
            self._loop.call_soon(task, value=self)

        # Add variable to update set
        self._loop.touch(self)

    value = property(fget=lambda self: NotImplemented)

    def changed(self) -> bool:
        """Return True if changed during the current time slot."""
        raise NotImplementedError()  # pragma: no cover

    def update(self) -> None:
        """Loop callback."""
        raise NotImplementedError()  # pragma: no cover


class Value(ABC):
    """Variable value."""

    def _get_prev(self) -> Any:
        raise NotImplementedError()  # pragma: no cover

    prev = property(fget=_get_prev)

    def _set_next(self, value: Any) -> None:
        raise NotImplementedError()  # pragma: no cover

    next = property(fset=_set_next)


class Singular(Variable, Value):
    """Model state organized as a single unit."""

    def __init__(self, value: Any):
        Variable.__init__(self)
        self._prev = value
        self._next = value
        self._changed: bool = False

    # Value
    def _get_prev(self) -> Any:
        return self._prev

    prev = property(fget=_get_prev)

    def _set_next(self, value: Any):
        self._changed = value != self._next
        self._next = value

        # Notify the event loop
        self._set()

    next = property(fset=_set_next)

    # Variable
    def _get_value(self):
        return self._next

    value = property(fget=_get_value)

    def changed(self) -> bool:
        return self._changed

    def update(self):
        self._prev = self._next
        self._changed = False


class Aggregate(Variable):
    """Model state organized as multiple units."""

    def __init__(self, value: Any):
        Variable.__init__(self)
        self._prevs: dict[Hashable, Any] = defaultdict(lambda: value)
        self._nexts: dict[Hashable, Any] = dict()

    # [key] => Value
    def __getitem__(self, key: Hashable) -> AggrItem:
        return AggrItem(self, key)

    def _get_prev(self, key: Hashable) -> Any:
        return self._prevs[key]

    def _get_next(self, key: Hashable) -> Any:
        try:
            return self._nexts[key]
        except KeyError:
            return self._prevs[key]

    def _set_next(self, key: Hashable, value: Any):
        if value != self._get_next(key):
            self._nexts[key] = value

        # Notify the event loop
        self._set()

    # Variable
    def _get_value(self) -> AggrValue:
        return AggrValue(self)

    value = property(fget=_get_value)

    def changed(self) -> bool:
        return bool(self._nexts)

    def update(self):
        while self._nexts:
            key, value = self._nexts.popitem()
            self._prevs[key] = value


class AggrItem(Value):
    """Wrap Aggregate __getitem__."""

    def __init__(self, aggr: Aggregate, key: Hashable):
        self._aggr = aggr
        self._key = key

    def _get_prev(self) -> Any:
        return self._aggr._get_prev(self._key)

    prev = property(fget=_get_prev)

    def _set_next(self, value: Any):
        self._aggr._set_next(self._key, value)

    next = property(fset=_set_next)


class AggrValue:
    """Wrap Aggregate value."""

    def __init__(self, aggr: Aggregate):
        self._aggr = aggr

    def __getitem__(self, key: Hashable) -> Any:
        return self._aggr._get_next(key)
