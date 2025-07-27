"""Model variables"""

from __future__ import annotations

from abc import ABC
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable, Generator, Hashable
from typing import Self

from ._kernel_if import KernelIf
from ._task import Blocking, Sendable, Task, TaskQueue

type Predicate = Callable[[], bool]


class _WaitQ(TaskQueue):
    """Tasks wait for variable touch."""

    def __init__(self):
        self._t2p: OrderedDict[Task, Predicate] = OrderedDict()
        self._items: deque[Task] = deque()

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[Task, Predicate]):
        task, p = item
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


class Variable(KernelIf, Blocking, Sendable):
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
        self._waiting = _WaitQ()

    def wait_push(self, task: Task, p: Predicate):
        self._waiting.push((task, p))

    def __await__(self) -> Generator[None, Sendable, Self]:
        """Await variable change:

        For variable ``v``:

        1. Suspend the current task.
        2. When another task invokes ``v.set_next(...)`` *and*
           ``v.changed()`` evaluates to ``True``,
           unblock all tasks waiting for that event.
        """
        task = self._kernel.task()
        # NOTE: Use default predicate
        self.wait_push(task, self.changed)
        v = yield from self._kernel.switch_gen()
        assert v is self
        return self

    def _set(self):
        self._waiting.load()

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))

        # Add variable to update set
        self._kernel.touch_var(self)

    def pred(self, p: Predicate) -> PredVar:
        """Return blocking, predicated variable.

        Args:
            p: Prediate function w/ no args and ``bool`` return type.

        Returns:
            Predicated Variable (``PredVar``) object.
        """
        return PredVar(self, p)

    def changed(self) -> bool:
        """Return True if changed during the current time slot."""
        raise NotImplementedError()  # pragma: no cover

    def update(self) -> None:
        raise NotImplementedError()  # pragma: no cover

    # Blocking
    def try_block(self, task: Task) -> bool:
        # NOTE: Use default predicate
        self.wait_push(task, self.changed)
        return True

    @property
    def s(self) -> Variable:
        return self

    # Sendable
    def cancel(self, task: Task):
        self._waiting.drop(task)


class PredVar(Blocking):
    """Predicated Variable.

    A lightweight wrapper around a Variable instance.
    Implements ``Awaitable`` and ``Blocking``.
    Can be used in ``await``, ``await AllOf`` and ``await AnyOf`` statements.

    Predicate functions allow fine-grained control of variable dependencies.
    Sometimes waiting tasks can be woken up when there is any change to the
    variables's value. However, it is often desirable to only trigger on
    particular types of changes. For example, in digital logic a flip-flop
    might only update its state when 1) reset is inactive, 2) clock is
    transitioning from low to high (a positive edge), AND 3) a data enable
    signal is active. A predicate function may be used to evaluate when
    those conditions are all true.
    """

    def __init__(self, var: Variable, p: Predicate):
        self._var = var
        self._p = p

    def __await__(self) -> Generator[None, Sendable, Variable]:
        """Await variable change:

        For variable ``v``, and predicate function ``p``:

        1. Suspend the current task.
        2. When another task invokes ``v.set_next(...)`` *and* ``p`` evaluates
           to ``True``, unblock all tasks waiting for that event.
        """
        task = self._var._kernel.task()
        self._var.wait_push(task, self._p)
        v = yield from self._var._kernel.switch_gen()
        assert v is self._var
        return self._var

    # Blocking
    def try_block(self, task: Task) -> bool:
        self._var.wait_push(task, self._p)
        return True

    @property
    def s(self) -> Sendable:
        return self._var


class Value[T](ABC):
    """Variable value."""

    def get_prev(self) -> T:
        """Return value at the end of the previous timeslot."""
        raise NotImplementedError()  # pragma: no cover

    prev = property(fget=get_prev)

    def set_next(self, value: T) -> None:
        """Schedule update to value in the current timeslot."""
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
        self._prevs: dict[Hashable, T] = defaultdict(lambda: value)
        self._nexts: dict[Hashable, T] = dict()

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
