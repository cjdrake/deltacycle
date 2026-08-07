"""Model variables"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Generator, Hashable
from typing import Any, Iterator, Self

from ._kernel_if import KernelIf
from ._task import Blocking, SupportsDropTask, Task

type Predicate = Callable[[], bool]


class _WaitQ(SupportsDropTask):
    """Tasks wait for variable touch."""

    def __init__(self):
        self._items: dict[Task[Any], list[PredVariable]] = {}

    def drop(self, task: Task[Any]):
        del self._items[task]
        task.unlink(tq=self)

    def push(self, task: Task[Any], pv: PredVariable):
        if task not in self._items:
            task.link(tq=self)
            self._items[task] = [pv]
        else:
            self._items[task].append(pv)

    def pop(self) -> Iterator[tuple[Task[Any], list[PredVariable], PredVariable]]:
        items: list[tuple[Task[Any], list[PredVariable], PredVariable]] = []

        for task, pvs in self._items.items():
            for pv in pvs:
                if pv:
                    items.append((task, pvs, pv))
                    break

        for item in items:
            self.drop(item[0])
            yield item


class Variable(KernelIf):
    """Model component that changes over time.

    The instantaneous state of a simulation is represented by a collection of variables.

    There are two types of variables: *singular*, and *aggregate*.

    Children::

               Variable
                  |
           +------+------+
           |             |
        Singular     Aggregate

    * A singular variable has one *value*.
    * An aggregate variable is a mapping of key, *value* pairs.

    Variables are *always* blocking.
    Tasks may schedule updates to variables.
    Changes to variable values may unblock tasks,
    which may in turn schedule updates to other variables.
    """

    def __init__(self):
        self._waitq = _WaitQ()

    def _set(self):
        for task, pvs, pv in self._waitq.pop():
            self._kernel.join_any(task, *pvs)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, pv))

        # Add variable to update set
        self._kernel.touch_var(self)

    def pred(self, p: Predicate | None = None) -> PredVariable:
        """Return blocking, predicated variable.

        Args:
            p: Predicate function with no args and ``bool`` return type.

        Returns:
            Predicated Variable object.
        """
        return PredVariable(self, p)

    @abstractmethod
    def changed(self) -> bool:
        """Return True if changed during the current time slot."""

    @abstractmethod
    def update(self) -> None:
        """Update variable value."""


class PredVariable(KernelIf, Blocking):
    """Predicated Variable.

    A lightweight wrapper around a Variable instance.
    Implements ``Awaitable`` and ``Blocking``.
    Can be used in ``await``, ``await AllOf`` and ``await AnyOf`` statements.

    Predicate functions allow fine-grained control of variable dependencies.
    Sometimes waiting tasks can be woken up when there is any change to the
    variable's value. However, it is often desirable to only trigger on
    particular types of changes. For example, in digital logic a flip-flop
    might only update its state when 1) reset is inactive, 2) clock is
    transitioning from low to high (a positive edge), AND 3) a data enable
    signal is active. A predicate function may be used to evaluate when
    those conditions are all true.
    """

    def __init__(self, v: Variable, p: Predicate | None = None):
        self._var = v
        if p is None:
            self._p = v.changed
        else:
            self._p = p

    @property
    def var(self) -> Variable:
        return self._var

    def __bool__(self) -> bool:
        return self._p()

    # Blocking
    def __await__(self) -> Generator[None, Self, None]:
        """Await variable change:

        For variable ``v``, and predicate function ``p``:

        1. Suspend the current task.
        2. When another task invokes ``v.set_next(...)`` *and* ``p`` evaluates
           to ``True``, unblock all tasks waiting for that event.
        """
        task = self._kernel.check_task()
        self._var._waitq.push(task, pv=self)
        pv = yield from task.switch_gen()
        assert pv is self

    def try_block(self, task: Task[Any]) -> bool:
        self._var._waitq.push(task, pv=self)
        return True

    def drop(self, task: Task[Any]):
        self._var._waitq.drop(task)


class Value[T](ABC):
    """Variable value."""

    @abstractmethod
    def get_prev(self) -> T:
        """Return value at the end of the previous timeslot."""

    prev = property(fget=get_prev)

    @abstractmethod
    def set_next(self, value: T) -> None:
        """Schedule update to value in the current timeslot."""

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
        """Return present value.

        When performing multiple updates to a variable during the same timeslot,
        this method will always return the value of the *latest* update.
        """
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
        self._prevs: defaultdict[Hashable, T] = defaultdict(lambda: value)
        self._nexts: dict[Hashable, T] = {}

    # [key] => Value
    def __getitem__(self, key: Hashable) -> AggrItem[T]:
        return AggrItem(self, key)

    def get_prev(self, key: Hashable) -> T:
        """Return value at the end of the previous timeslot."""
        return self._prevs[key]

    def get_next(self, key: Hashable) -> T:
        try:
            return self._nexts[key]
        except KeyError:
            return self._prevs[key]

    def set_next(self, key: Hashable, value: T):
        """Schedule update to value in the current timeslot."""
        if value != self.get_next(key):
            self._nexts[key] = value

        # Notify the kernel
        self._set()

    # Variable
    def get_value(self) -> AggrValue[T]:
        """Return present value.

        When performing multiple updates to a variable during the same timeslot,
        this method will always return the value of the *latest* update.
        """
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
