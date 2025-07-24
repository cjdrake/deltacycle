"""Model variables"""

from __future__ import annotations

from abc import ABC
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable, Generator, Hashable
from typing import Self

from ._kernel_if import KernelIf
from ._task import Cancellable, Schedulable, Task, TaskQueue

type Predicate = Callable[[], bool]


class _VarWaitQ(TaskQueue):
    """Tasks wait for variable touch."""

    def __init__(self):
        self._t2p: OrderedDict[Task, Predicate] = OrderedDict()
        self._items: deque[Task] = deque()

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[Predicate, Task]):
        p, task = item
        task._link(self)
        self._t2p[task] = p

    def pop(self) -> Task:
        task = self._items.popleft()
        self.drop(task)
        return task

    def drop(self, task: Task):
        del self._t2p[task]
        task._unlink(self)

    def load(self):
        assert not self._items
        self._items.extend(t for t, p in self._t2p.items() if p())


class Variable(KernelIf, Schedulable, Cancellable):
    """Model component.

    Children::

               Variable
                  |
           +------+------+
           |             |
        Singular     Aggregate
    """

    def __init__(self):
        self._waiting = _VarWaitQ()

    def wait_push(self, p: Predicate, t: Task):
        self._waiting.push((p, t))

    def __await__(self) -> Generator[None, Cancellable, Self]:
        task = self._kernel.task()
        # NOTE: Use default predicate
        self.wait_push(self.changed, task)
        v = yield from self._kernel.switch_gen()
        assert v is self
        return self

    def blocking(self) -> bool:
        return True

    def schedule(self, task: Task):
        # NOTE: Use default predicate
        self.wait_push(self.changed, task)

    @property
    def c(self) -> Variable:
        return self

    def cancel(self, task: Task):
        self._waiting.drop(task)

    def _set(self):
        self._waiting.load()

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))

        # Add variable to update set
        self._kernel.touch(self)

    def pred(self, p: Predicate) -> PredVar:
        return PredVar(self, p)

    def changed(self) -> bool:
        """Return True if changed during the current time slot."""
        raise NotImplementedError()  # pragma: no cover

    def update(self) -> None:
        """Kernel callback."""
        raise NotImplementedError()  # pragma: no cover


class PredVar(Schedulable):
    """Predicated Variable."""

    def __init__(self, v: Variable, p: Predicate):
        self._v = v
        self._p = p

    def __await__(self) -> Generator[None, Cancellable, Variable]:
        task = self._v._kernel.task()
        self._v.wait_push(self._p, task)
        v = yield from self._v._kernel.switch_gen()
        assert v is self._v
        return self._v

    def blocking(self) -> bool:
        return True

    def schedule(self, task: Task):
        self._v.wait_push(self._p, task)

    @property
    def c(self) -> Cancellable:
        return self._v


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

        # Notify the kernel
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

        # Notify the kernel
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
