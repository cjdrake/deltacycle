"""Model variables"""

from __future__ import annotations

from abc import ABC
from collections import defaultdict
from collections.abc import Generator, Hashable

from ._loop_if import LoopIf
from ._task import Predicate, Task, TaskCommand, WaitSet


class Variable(LoopIf):
    """Model component.

    Children::

               Variable
                  |
           +------+------+
           |             |
        Singular     Aggregate
    """

    def __init__(self):
        self._waiting = WaitSet()

    def __await__(self) -> Generator[None, Variable, Variable]:
        task = self._loop.task()
        self._wait(self.changed, task)
        v = yield from self._loop.switch_gen()
        assert v is self
        return self

    def _wait(self, p: Predicate, task: Task):
        self._waiting.push((p, task))
        self._loop._task2vars[task].add(self)

    def _set(self):
        self._waiting.set()

        while self._waiting:
            task = self._waiting.pop()

            # Remove task from Variable waiting queues
            self._loop._task2vars[task].remove(self)
            while self._loop._task2vars[task]:
                v = self._loop._task2vars[task].pop()
                v._waiting.drop(task)
            del self._loop._task2vars[task]

            # Send variable id to parent task
            self._loop.call_soon(task, value=(TaskCommand.RESUME, self))

        # Add variable to update set
        self._loop.touch(self)

    def changed(self) -> bool:
        """Return True if changed during the current time slot."""
        raise NotImplementedError()  # pragma: no cover

    def update(self) -> None:
        """Loop callback."""
        raise NotImplementedError()  # pragma: no cover


class Value[T](ABC):
    """Variable value."""

    def get_prev(self) -> T:
        raise NotImplementedError()  # pragma: no cover

    prev = property(fget=get_prev)

    def set_next(self, value: T) -> None:
        raise NotImplementedError()  # pragma: no cover

    next = property(fset=set_next)


class Singular[T](Variable, Value[T]):
    """Model state organized as a single unit."""

    def __init__(self, value: T):
        Variable.__init__(self)
        self._prev = value
        self._next = value
        self._changed: bool = False

    # Value
    def get_prev(self) -> T:
        return self._prev

    prev = property(fget=get_prev)

    def set_next(self, value: T):
        self._changed = value != self._next
        self._next = value

        # Notify the event loop
        self._set()

    next = property(fset=set_next)

    # Variable
    def get_value(self) -> T:
        return self._next

    value = property(fget=get_value)

    def changed(self) -> bool:
        return self._changed

    def update(self):
        self._prev = self._next
        self._changed = False


class Aggregate[T](Variable):
    """Model state organized as multiple units."""

    def __init__(self, value: T):
        Variable.__init__(self)
        self._prevs: dict[Hashable, T] = defaultdict(lambda: value)
        self._nexts: dict[Hashable, T] = dict()

    # [key] => Value
    def __getitem__(self, key: Hashable) -> AggrItem[T]:
        return AggrItem(self, key)

    def get_prev(self, key: Hashable) -> T:
        return self._prevs[key]

    def get_next(self, key: Hashable) -> T:
        try:
            return self._nexts[key]
        except KeyError:
            return self._prevs[key]

    def set_next(self, key: Hashable, value: T):
        if value != self.get_next(key):
            self._nexts[key] = value

        # Notify the event loop
        self._set()

    # Variable
    def get_value(self) -> AggrValue[T]:
        return AggrValue(self)

    value = property(fget=get_value)

    def changed(self) -> bool:
        return bool(self._nexts)

    def update(self):
        while self._nexts:
            key, value = self._nexts.popitem()
            self._prevs[key] = value


class AggrItem[T](Value[T]):
    """Wrap Aggregate __getitem__."""

    def __init__(self, aggr: Aggregate[T], key: Hashable):
        self._aggr = aggr
        self._key = key

    def get_prev(self) -> T:
        return self._aggr.get_prev(self._key)

    prev = property(fget=get_prev)

    def set_next(self, value: T):
        self._aggr.set_next(self._key, value)

    next = property(fset=set_next)


class AggrValue[T]:
    """Wrap Aggregate value."""

    def __init__(self, aggr: Aggregate[T]):
        self._aggr = aggr

    def __getitem__(self, key: Hashable) -> T:
        return self._aggr.get_next(key)
