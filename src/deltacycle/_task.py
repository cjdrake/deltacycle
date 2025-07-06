"""Task: coroutine wrapper"""

from __future__ import annotations

import heapq
import logging
from abc import ABC
from collections import Counter, deque
from collections.abc import Callable, Coroutine, Generator
from enum import IntEnum
from types import TracebackType
from typing import Any

from ._kernel_if import KernelIf

logger = logging.getLogger("deltacycle")

type Predicate = Callable[[], bool]

# TODO(cjdrake): Restrict SendType?
type TaskCoro = Coroutine[None, Any, Any]


class Signal(Exception):
    pass


class Interrupt(Signal):
    """Interrupt task."""


class _Kill(Signal):
    """Kill task."""


class TaskQueueIf(ABC):
    def __bool__(self) -> bool:
        """Return True if the queue has tasks ready to run."""
        raise NotImplementedError()  # pragma: no cover

    def push(self, item: Any) -> None:
        raise NotImplementedError()  # pragma: no cover

    def pop(self) -> Any:
        raise NotImplementedError()  # pragma: no cover

    def drop(self, task: Task) -> None:
        """If a task reneges, drop it from the queue."""
        raise NotImplementedError()  # pragma: no cover


class PendQueue(TaskQueueIf):
    """Priority queue for ordering task execution."""

    def __init__(self):
        # time, priority, index, task, value
        self._items: list[tuple[int, int, int, Task, Any]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[int, Task, Any]):
        time, task, value = item
        task._link(self)
        heapq.heappush(self._items, (time, task.priority, self._index, task, value))
        self._index += 1

    def pop(self) -> tuple[Task, Any]:
        _, _, _, task, value = heapq.heappop(self._items)
        task._unlink(self)
        return (task, value)

    def _find(self, task: Task) -> int:
        for i, (_, _, _, t, _) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task):
        index = self._find(task)
        self._items.pop(index)
        task._unlink(self)

    def peek(self) -> int:
        return self._items[0][0]

    def clear(self):
        while self._items:
            self.pop()
        self._index = 0


class WaitFifo(TaskQueueIf):
    """Tasks wait in FIFO order."""

    def __init__(self):
        self._items: deque[Task] = deque()

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: Task):
        task = item
        task._link(self)
        self._items.append(task)

    def pop(self) -> Task:
        task = self._items.popleft()
        task._unlink(self)
        return task

    def drop(self, task: Task):
        self._items.remove(task)
        task._unlink(self)


class WaitSet(TaskQueueIf):
    """Tasks wait for variable touch."""

    def __init__(self):
        self._tps: dict[Task, Predicate] = dict()
        self._items: set[Task] = set()

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[Predicate, Task]):
        p, task = item
        task._link(self)
        self._tps[task] = p

    def pop(self) -> Task:
        task = self._items.pop()
        self.drop(task)
        return task

    def drop(self, task: Task):
        del self._tps[task]
        task._unlink(self)

    def set(self):
        assert not self._items
        self._items.update(t for t, p in self._tps.items() if p())


class Task(KernelIf):
    """Manage the life cycle of a coroutine.

    Do NOT instantiate a Task directly.
    Use ``create_task`` function, or (better) ``TaskGroup.create_task`` method.
    """

    class Command(IntEnum):
        START = 0b00
        RESUME = 0b01
        INTERRUPT = 0b10
        KILL = 0b11

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
        priority: int,
    ):
        self._state = self.State.INIT

        # Attributes
        self._coro = coro
        self._name = name
        self._priority = priority

        # Set if created within a group
        self._group: TaskGroup | None = None

        # Keep track of all queues containing this task
        self._refcnts: Counter[TaskQueueIf] = Counter()

        # Other tasks waiting for this task to complete
        self._waiting = WaitFifo()

        # Flag to avoid multiple signals
        self._signal = False

        # Outputs
        self._result: Any = None
        self._exception: Exception | None = None

    def __await__(self) -> Generator[None, Task, Any]:
        if not self.done():
            task = self._kernel.task()
            self._wait(task)
            t = yield from self._kernel.switch_gen()
            assert isinstance(t, Task)
            assert t is self

        # Resume
        return self.result()

    def _wait(self, task: Task):
        self._waiting.push(task)

    def _set(self):
        while self._waiting:
            task = self._waiting.pop()
            # Send child id to parent task
            self._kernel.call_soon(task, value=(self.Command.RESUME, self))

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

    @property
    def priority(self) -> int:
        """Task priority.

        Tasks in the same time slot are executed in priority order.
        Low values execute *before* high values.

        For example,
        a task scheduled to run at time 42 with priority -1 will execute
        *before* a task scheduled to run at time 42 with priority +1.

        If not provided to the create_task function,
        a default priority of zero will be assigned.
        """
        return self._priority

    def _get_group(self) -> TaskGroup | None:
        return self._group

    def _set_group(self, group: TaskGroup):
        self._group = group

    group = property(fget=_get_group, fset=_set_group)

    def _set_state(self, state: State):
        assert state in self._state_transitions[self._state]
        logger.debug("%s: %s => %s", self.name, self._state.name, state.name)
        self._state = state

    def state(self) -> State:
        return self._state

    def _link(self, tq: TaskQueueIf):
        self._refcnts[tq] += 1

    def _unlink(self, tq: TaskQueueIf):
        assert self._refcnts[tq] > 0
        self._refcnts[tq] -= 1

    def _renege(self):
        tqs = set(self._refcnts.keys())
        while tqs:
            tq = tqs.pop()
            while self._refcnts[tq]:
                tq.drop(self)
            del self._refcnts[tq]

    def _do_run(self, args: tuple[Command] | tuple[Command, Any]):
        self._set_state(self.State.RUNNING)

        match args:
            case (self.Command.START,):
                y = self._coro.send(None)
            case (self.Command.RESUME,):
                y = self._coro.send(None)
            case (self.Command.RESUME, aw):
                y = self._coro.send(aw)
            case (self.Command.INTERRUPT, irq):
                self._signal = False
                y = self._coro.throw(irq)
            case (self.Command.KILL, kill):
                self._signal = False
                y = self._coro.throw(kill)
            case _:  # pragma: no cover
                assert False

        # TaskCoro YieldType=None
        assert y is None

    def _do_result(self, exc: StopIteration):
        self._result = exc.value
        self._set_state(self.State.RETURNED)
        self._set()
        assert self._refcnts.total() == 0

    def _do_except(self, exc: Exception):
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
        self._kernel.call_soon(self, value=(self.Command.INTERRUPT, irq))

        # Success
        return True

    def _kill(self) -> bool:
        # Already done; do nothing
        if self._signal or self.done():
            return False

        # Task cannot kill itself
        assert self is not self._kernel.task()

        # Pending tasks must first renege from queues
        self._renege()

        # Reschedule
        self._signal = True
        self._kernel.call_soon(self, value=(self.Command.KILL, _Kill()))

        # Success
        return True


class TaskGroup(KernelIf):
    """Group of tasks."""

    def __init__(self):
        self._parent = self._kernel.task()

        # Tasks started in the with block
        self._setup_done = False
        self._setup_tasks: set[Task] = set()

        # Tasks in running/pending/killing state
        self._awaited: set[Task] = set()

    async def __aenter__(self) -> TaskGroup:
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
                self._awaited.add(child)
                child._wait(self._parent)

        # Parent raised an exception:
        # Kill children; suppress exceptions
        if exc:
            for child in self._awaited:
                child._kill()
            while self._awaited:
                child = await self._kernel.switch_coro()
                assert isinstance(child, Task)
                self._awaited.remove(child)

            # Re-raise parent exception
            return False

        # Parent did NOT raise an exception:
        # Await children; collect exceptions
        child_excs: list[Exception] = []
        killed: set[Task] = set()
        while self._awaited:
            child = await self._kernel.switch_coro()
            assert isinstance(child, Task)
            self._awaited.remove(child)
            if child in killed:
                continue
            exc = child.exception()
            if exc is not None:
                child_excs.append(exc)
                killed.update(c for c in self._awaited if c._kill())

        # Re-raise child exceptions
        if child_excs:
            raise ExceptionGroup("Child task(s) raised exception(s)", child_excs)

    def create_task(
        self,
        coro: TaskCoro,
        name: str | None = None,
        priority: int = 0,
    ) -> Task:
        child = self._kernel.create_task(coro, name, priority)
        child.group = self
        if self._setup_done:
            self._awaited.add(child)
            child._wait(self._parent)
        else:
            self._setup_tasks.add(child)
        return child
