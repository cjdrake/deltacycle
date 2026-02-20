"""Task: coroutine wrapper"""

from __future__ import annotations

import heapq
from abc import ABC, abstractmethod
from collections import Counter, OrderedDict, deque
from collections.abc import Coroutine, Generator
from enum import IntEnum
from types import TracebackType
from typing import Any, Self

from ._kernel_if import KernelIf

type TaskCoro = Coroutine[None, Sendable | None, Any]
type TaskArgs = tuple[Task.Command] | tuple[Task.Command, Sendable | Throwable]


class Throwable(Exception):
    """Throw a signal to a task."""


class Interrupt(Throwable):
    """Interrupt task."""


class _Kill(Throwable):
    """Kill task."""


class TaskQueue(ABC):
    @abstractmethod
    def __bool__(self) -> bool:
        """Return True if the queue has tasks ready to run."""

    @abstractmethod
    def push(self, item: Any) -> None:
        """Push item to queue tail."""

    @abstractmethod
    def pop(self) -> Any:
        """Pop item from queue head."""

    @abstractmethod
    def drop(self, task: Task) -> None:
        """Drop task from queue."""


class EventQ(TaskQueue):
    """Tasks wait for event trigger."""

    def __init__(self):
        self._tasks = OrderedDict[Task, None]()
        self._items = deque[Task]()

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: Task):
        item.link(self)
        self._tasks[item] = None

    def pop(self) -> Task:
        task = self._items.popleft()
        self.drop(task)
        return task

    def drop(self, task: Task):
        del self._tasks[task]
        task.unlink(self)

    def load(self):
        assert not self._items
        self._items.extend(self._tasks)


class SemaphoreQ(TaskQueue):
    """Tasks wait for a slot to become available."""

    def __init__(self):
        # priority, index, task
        self._items = list[tuple[int, int, Task]]()

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[int, Task]):
        priority, task = item
        task.link(self)
        heapq.heappush(self._items, (priority, self._index, task))
        self._index += 1

    def pop(self) -> Task:
        _, _, task = heapq.heappop(self._items)
        task.unlink(self)
        return task

    def _find(self, task: Task) -> int:
        for i, (_, _, t) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task):
        index = self._find(task)
        self._items.pop(index)
        task.unlink(self)


class CreditQ(TaskQueue):
    """Tasks wait for credit to become available."""

    def __init__(self):
        # priority, index, task, n
        self._items = list[tuple[int, int, Task, int]]()

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[int, Task, int]):
        priority, task, n = item
        task.link(self)
        heapq.heappush(self._items, (priority, self._index, task, n))
        self._index += 1

    def pop(self) -> tuple[Task, int]:
        _, _, task, n = heapq.heappop(self._items)
        task.unlink(self)
        return task, n

    def _find(self, task: Task) -> int:
        for i, (_, _, t, _) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task):
        index = self._find(task)
        self._items.pop(index)
        task.unlink(self)

    def peek(self) -> int:
        assert self._items
        return self._items[0][-1]


class Blocking(ABC):
    @abstractmethod
    def try_block(self, task: Task) -> bool:
        """Attempt to block task; return True if successful."""

    @property
    @abstractmethod
    def x(self) -> Sendable:
        """Object that will be sent to unblock task."""


class Sendable(ABC):
    @abstractmethod
    def wait_drop(self, task: Task) -> None:
        """Drop task from object's waiting queue."""


class _SuspendResume:
    """Suspend/Resume current task.

    Use case:
    1. Current task A suspends itself: RUNNING => WAITING
    2. Kernel chooses PENDING tasks ..., T
    3. ... Task T wakes up task A w/ value X: WAITING => PENDING
    4. Kernel chooses PENDING tasks ..., A: PENDING => RUNNING
    5. Task A resumes with value X

    The value X can be used to pass information to the task.
    """

    def __await__(self) -> Generator[None, Sendable | None, Sendable | None]:
        # Suspend
        value = yield
        # Resume
        return value


class _Condition(KernelIf):
    def __init__(self, *bs: Blocking):
        self._bs = bs


class AllOf(_Condition):
    def __await__(self) -> Generator[None, Sendable, tuple[Sendable, ...]]:
        task = self._kernel.task()

        blocked = set[Sendable]()
        unblocked = deque[Sendable]()

        for b in self._bs:
            if b.try_block(task):
                blocked.add(b.x)
            else:
                unblocked.append(b.x)

        while blocked:
            x = yield from task.switch_gen()
            blocked.remove(x)
            unblocked.append(x)

        return tuple(unblocked)


class AnyOf(_Condition):
    def __await__(self) -> Generator[None, Sendable, Sendable | None]:
        if not self._bs:
            return None

        task = self._kernel.task()

        blocked = set[Sendable]()

        for b in self._bs:
            if b.try_block(task):
                blocked.add(b.x)
            else:
                while blocked:
                    x = blocked.pop()
                    x.wait_drop(task)
                return b.x

        self._kernel.fork(task, *blocked)
        x = yield from task.switch_gen()
        return x


class Task(KernelIf, Blocking, Sendable):
    """Manage the life cycle of a coroutine.

    Do NOT instantiate a Task directly.
    Use ``create_task`` function, or (better) ``TaskGroup.create_task`` method.
    """

    class Command(IntEnum):
        START = 0b00
        RESUME = 0b01
        SIGNAL = 0b10

    class State(IntEnum):
        """
        Transitions::

                    PENDING
                       |
            INIT -> RUNNING -> RETURNED
                            -> EXCEPTED
        """

        # Initialized
        INIT = 0b001

        # Currently running
        RUNNING = 0b010

        # Suspended
        PENDING = 0b011

        # Done: returned a result
        RETURNED = 0b100
        # Done: raised an exception
        EXCEPTED = 0b101

    _done = State.RETURNED & State.EXCEPTED

    _state_transitions = {
        State.INIT: {
            State.RUNNING,
        },
        State.RUNNING: {
            State.PENDING,
            State.RETURNED,
            State.EXCEPTED,
        },
        State.PENDING: {
            State.RUNNING,
        },
    }

    def __init__(
        self,
        coro: TaskCoro,
        name: str,
    ):
        self._state = self.State.INIT

        # Attributes
        self._coro = coro
        self._name = name

        # Set if created within a group
        self._group: TaskGroup | None = None

        # Keep track of all queues containing this task
        self._refcnts = Counter[TaskQueue]()

        # Other tasks waiting for this task to complete
        self._waiting = EventQ()

        # Flag to avoid multiple signals
        self._signal = False

        # Outputs
        self._result: Any = None
        self._exception: Exception | None = None

    def _blocking(self) -> bool:
        return not self.done()

    def wait_push(self, task: Task):
        self._waiting.push(task)

    def wait_drop(self, task: Task):
        self._waiting.drop(task)

    def __await__(self) -> Generator[None, Sendable, Any]:
        if self._blocking():
            task = self._kernel.task()
            self.wait_push(task)
            t = yield from task.switch_gen()
            assert t is self

        return self.result()

    @property
    def coro(self) -> TaskCoro:
        """Wrapped coroutine."""
        return self._coro

    @property
    def name(self) -> str:
        """Task name.

        Primarily for debug; no functional effect.
        There are no rules or restrictions for valid names.
        Give tasks unique and recognizable names to help identify them.

        If not provided to the create_task function,
        a default name of ``Task-{index}`` will be assigned,
        where ``index`` is a monotonically increasing integer value,
        starting from 0.
        """
        return self._name

    def _get_group(self) -> TaskGroup | None:
        """Return TaskGroup, or None.

        If the task was started by a TaskGroup's create_task method,
        it will assign this property to point to the TaskGroup instance.
        """
        return self._group

    def _set_group(self, group: TaskGroup):
        self._group = group

    group = property(fget=_get_group, fset=_set_group)

    def _set_state(self, state: State):
        assert state in self._state_transitions[self._state]
        self._state = state

    def state(self) -> State:
        return self._state

    def link(self, tq: TaskQueue):
        self._refcnts[tq] += 1

    def unlink(self, tq: TaskQueue):
        assert self._refcnts[tq] > 0
        self._refcnts[tq] -= 1

    def _renege(self):
        tqs = set(self._refcnts.keys())
        while tqs:
            tq = tqs.pop()
            while self._refcnts[tq]:
                tq.drop(self)
            del self._refcnts[tq]

    async def switch_coro(self) -> Sendable | None:
        self._set_state(Task.State.PENDING)

        # Suspend
        value = await _SuspendResume()
        # Resume
        return value

    def switch_gen(self) -> Generator[None, Sendable, Sendable]:
        self._set_state(self.State.PENDING)

        # Suspend
        value = yield
        # Resume
        return value

    def do_run(self, args: TaskArgs):
        self._set_state(self.State.RUNNING)

        match args:
            case (self.Command.START,):
                y = self._coro.send(None)
            case (self.Command.RESUME,):
                y = self._coro.send(None)
            case (self.Command.RESUME, Sendable() as x):
                y = self._coro.send(x)
            case (self.Command.SIGNAL, Throwable() as x):
                self._signal = False
                y = self._coro.throw(x)
            case _:  # pragma: no cover
                assert False

        # TaskCoro YieldType=None
        assert y is None

    def _set(self):
        self._waiting.load()

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(self.Command.RESUME, self))

    def do_result(self, exc: StopIteration):
        self._result = exc.value
        self._set_state(self.State.RETURNED)
        self._set()
        assert self._refcnts.total() == 0

    def do_except(self, exc: Exception):
        self._exception = exc
        self._set_state(self.State.EXCEPTED)
        self._set()
        assert self._refcnts.total() == 0

    def done(self) -> bool:
        """Return True if the task is done.

        A task that is "done" either:

        * Completed normally, or
        * Raised an exception.
        """
        return bool(self._state & self._done)

    def result(self) -> Any:
        """Return the task's result, or raise an exception.

        Returns:
            If the task ran to completion, return its result.

        Raises:
            Exception: If the task raise any other type of exception.
            RuntimeError: If the task is not done.
        """
        if self._state is self.State.RETURNED:
            assert self._exception is None
            return self._result
        if self._state is self.State.EXCEPTED:
            assert self._result is None and self._exception is not None
            raise self._exception
        raise RuntimeError("Task is not done")

    def exception(self) -> Exception | None:
        """Return the task's exception.

        Returns:
            If the task raised an exception, return it.
            Otherwise, return None.

        Raises:
            RuntimeError: If the task is not done.
        """
        if self._state is self.State.RETURNED:
            assert self._exception is None
            return self._exception
        if self._state is self.State.EXCEPTED:
            assert self._result is None and self._exception is not None
            return self._exception
        raise RuntimeError("Task is not done")

    def interrupt(self, *args: Any) -> bool:
        """Interrupt task.

        If a task is already done: return False.

        If a task is pending:

        1. Renege from all queues
        2. Reschedule to raise Interrupt in the current time slot
        3. Return True

        If a task is running, immediately raise Interrupt.

        Args:
            args: Arguments passed to Interrupt instance

        Returns:
            bool success indicator

        Raises:
            Interrupt: If the task interrupts itself
        """
        # Already done; do nothing
        if self._signal or self.done():
            return False

        irq = Interrupt(*args)

        # Task is interrupting itself. Weird, but legal.
        if self is self._kernel.task():
            raise irq

        # Pending tasks must first renege from queues
        self._renege()

        # Reschedule
        self._signal = True
        self._kernel.call_soon(self, args=(self.Command.SIGNAL, irq))

        # Success
        return True

    def kill(self) -> bool:
        # Already done; do nothing
        if self._signal or self.done():
            return False

        # Task cannot kill itself
        assert self is not self._kernel.task()

        # Pending tasks must first renege from queues
        self._renege()

        # Reschedule
        self._signal = True
        self._kernel.call_soon(self, args=(self.Command.SIGNAL, _Kill()))

        # Success
        return True

    # Blocking
    def try_block(self, task: Task) -> bool:
        if self._blocking():
            self.wait_push(task)
            return True
        return False

    @property
    def x(self) -> Task:
        return self


class TaskGroup(KernelIf):
    """Group of tasks."""

    def __init__(self):
        self._parent = self._kernel.task()

        # Tasks started in the with block
        self._setup_done = False
        self._setup_tasks = set[Task]()

        # Tasks in running/pending/killing state
        self._todo = set[Task]()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception] | None,
        exc: Exception | None,
        traceback: TracebackType | None,
    ):
        self._setup_done = True

        # Start newly created tasks; ignore exceptions handled by parent
        while self._setup_tasks:
            child = self._setup_tasks.pop()
            if not child.done():
                child.wait_push(self._parent)
                self._todo.add(child)

        # Parent raised an exception:
        # Kill children; suppress exceptions
        if exc:
            for child in self._todo:
                child.kill()
            while self._todo:
                child = await self._parent.switch_coro()
                assert isinstance(child, Task)
                self._todo.remove(child)

            # Re-raise parent exception
            return False

        # Parent did NOT raise an exception:
        # Await children; collect exceptions
        child_excs = list[Exception]()
        killed = set[Task]()
        while self._todo:
            child = await self._parent.switch_coro()
            assert isinstance(child, Task)
            self._todo.remove(child)
            if child in killed:
                continue
            exc = child.exception()
            if exc is not None:
                child_excs.append(exc)
                killed.update(c for c in self._todo if c.kill())

        # Re-raise child exceptions
        if child_excs:
            raise ExceptionGroup("Child task(s) raised exception(s)", child_excs)

    def create_task(
        self,
        coro: TaskCoro,
        name: str | None = None,
        **kwargs: Any,
    ) -> Task:
        child = self._kernel.create_task(coro, name, **kwargs)
        child.group = self
        if self._setup_done:
            if not child.done():
                child.wait_push(self._parent)
                self._todo.add(child)
        else:
            self._setup_tasks.add(child)
        return child
