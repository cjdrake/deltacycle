"""Model variables"""

# pylint: disable=protected-access

from __future__ import annotations

from abc import ABC
from collections import defaultdict
from collections.abc import Hashable
from typing import Any

from ._loop_if import LoopIf
from ._task import Predicate, Task, TaskState, WaitTouchIf


class Variable(LoopIf, WaitTouchIf):
    """Model component."""

    def __init__(self):
        WaitTouchIf.__init__(self)

    def wait(self, task: Task, p: Predicate | None = None):
        if p is None:
            self.add_task(task, self.changed)
        else:
            self.add_task(task, p)

    def _touch(self):
        for task in self.pend_tasks():
            self.remove_task(task)
            match task.state():
                case TaskState.PENDING:
                    pass
                case TaskState.WAITING:
                    self._loop.call_soon(task, value=self)
                case _:  # pragma: no cover
                    assert False

        # Add variable to update set
        self._loop.touch(self)

    value = property(fget=lambda self: NotImplemented)

    def changed(self) -> bool:
        raise NotImplementedError()  # pragma: no cover

    def update(self):
        raise NotImplementedError()  # pragma: no cover


class Value(ABC):
    """Variable value."""

    def _get_prev(self) -> Any:
        raise NotImplementedError()  # pragma: no cover

    prev = property(fget=_get_prev)

    def _set_next(self, value: Any):
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
        self._touch()

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

    def _set_next(self, key: Hashable, value):
        if value != self._get_next(key):
            self._nexts[key] = value

        # Notify the event loop
        self._touch()

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
