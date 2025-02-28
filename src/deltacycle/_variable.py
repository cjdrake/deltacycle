"""TODO(cjdrake): Write docstring."""

# pylint: disable=protected-access

from __future__ import annotations

from abc import ABC
from collections import defaultdict
from collections.abc import Awaitable, Callable, Generator, Hashable
from typing import Any

from ._task import Task, TaskState

type Predicate = Callable[[], bool]


def _loop():
    from ._loop import get_running_loop  # pylint: disable=import-outside-toplevel

    return get_running_loop()


class Variable(Awaitable):
    """Model component."""

    def __init__(self):
        self._waiting: set[Task] = set()
        self._predicates: dict[Task, Predicate] = dict()

    def __await__(self) -> Generator[None, Variable, Variable]:
        loop = _loop()
        task = loop.task()

        self.add_task(task)
        task.add_parent(self)

        # Suspend
        task.set_state(TaskState.WAITING)
        v = yield

        # Resume
        assert v is self
        task.remove_parent(v)
        return v

    value = property(fget=lambda s: NotImplemented)

    def add_task(self, task: Task, predicate: Predicate | None = None):
        self._waiting.add(task)
        if predicate is None:
            self._predicates[task] = self.changed
        else:
            self._predicates[task] = predicate

    def remove_task(self, task: Task):
        self._waiting.remove(task)
        del self._predicates[task]

    def touch(self):
        loop = _loop()
        pending = [task for task in self._waiting if self._predicates[task]()]
        for task in pending:
            self.remove_task(task)
            loop.call_soon(task, value=self)
        loop.model_touch(self)

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
    """Model component organized as a single unit."""

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
        self.touch()

    next = property(fset=_set_next)

    # Variable
    def _get_value(self) -> Any:
        return self._next

    value = property(fget=_get_value)

    def changed(self) -> bool:
        return self._changed

    def update(self):
        self._prev = self._next
        self._changed = False

    # Other
    def dirty(self) -> bool:
        return self._next != self._prev


class Aggregate(Variable):
    """Model component organized as multiple units."""

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
        self.touch()

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
    """Wrap Aggregate Value."""

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
    """Wrap Aggregate _get_next."""

    def __init__(self, aggr: Aggregate):
        self._aggr = aggr

    def __getitem__(self, key: Hashable) -> Any:
        return self._aggr._get_next(key)
