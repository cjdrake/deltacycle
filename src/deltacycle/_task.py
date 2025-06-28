"""Task: coroutine wrapper"""

from __future__ import annotations

import heapq
import logging
from abc import ABC
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Coroutine, Generator
from enum import IntEnum, auto
from types import TracebackType
from typing import Any

from ._loop_if import LoopIf

logger = logging.getLogger("deltacycle")

type Predicate = Callable[[], bool]

# TODO(cjdrake): Restrict SendType?
type TaskCoro = Coroutine[None, Any, Any]
type TaskGen = Generator[None, Task, Any]


class CancelledError(Exception):
    """Task has been cancelled."""


class TaskStateError(Exception):
    """Task has an invalid state."""


class TaskCommand(IntEnum):
    """Task Run Command."""

    START = auto()
    SEND = auto()
    CANCEL = auto()


class TaskState(IntEnum):
    """Task State

    Transitions::

        INIT -> RUNNING -> RESULTED
                        -> CANCELLED
                        -> EXCEPTED
    """

    # Initialized
    INIT = auto()

    # Currently running
    RUNNING = auto()

    # Done: returned a result
    RESULTED = auto()
    # Done: cancelled
    CANCELLED = auto()
    # Done: raised an exception
    EXCEPTED = auto()


_task_state_transitions = {
    TaskState.INIT: {
        TaskState.RUNNING,
        TaskState.CANCELLED,
    },
    TaskState.RUNNING: {
        TaskState.RESULTED,
        TaskState.CANCELLED,
        TaskState.EXCEPTED,
    },
}


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


class Task(Awaitable[Any], LoopIf):
    """Manage the life cycle of a coroutine.

    Do NOT instantiate a Task directly.
    Use ``create_task`` function, or (better) ``TaskGroup.create_task`` method.
    """

    def __init__(
        self,
        coro: TaskCoro,
        name: str,
        priority: int,
    ):
        self._state = TaskState.INIT

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

        # Flag to avoid multiple cancellation
        self._cancelling = False

        # Outputs
        self._result: Any = None
        self._exception: Exception | None = None

    def __await__(self) -> TaskGen:
        if not self.done():
            task = self._loop.task()
            self._wait(task)
            t: Task = yield from self._loop.switch_gen()
            assert t is self

        # Resume
        return self.result()

    def _wait(self, task: Task):
        self._waiting.push(task)

    def _set(self):
        while self._waiting:
            task = self._waiting.pop()
            # Send child id to parent task
            self._loop.call_soon(task, value=(TaskCommand.SEND, self))

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

    @property
    def group(self) -> TaskGroup | None:
        return self._group

    def _set_state(self, state: TaskState):
        assert state in _task_state_transitions[self._state]
        logger.debug("%s: %s => %s", self.name, self._state.name, state.name)
        self._state = state

    def state(self) -> TaskState:
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

    def _do_run(self, cmd: TaskCommand, arg):
        match cmd:
            case TaskCommand.START:
                self._set_state(TaskState.RUNNING)
                y = self._coro.send(None)
            case TaskCommand.SEND:
                y = self._coro.send(arg)
            case TaskCommand.CANCEL:
                self._cancelling = False
                y = self._coro.throw(arg)
            case _:  # pragma: no cover
                assert False

        # TaskCoro YieldType=None
        assert y is None

    def _do_result(self, exc: StopIteration):
        self._result = exc.value
        self._set_state(TaskState.RESULTED)
        self._set()
        assert self._refcnts.total() == 0

    def _do_cancel(self, exc: CancelledError):
        self._exception = exc
        self._set_state(TaskState.CANCELLED)
        self._set()
        assert self._refcnts.total() == 0

    def _do_except(self, exc: Exception):
        self._exception = exc
        self._set_state(TaskState.EXCEPTED)
        self._set()
        assert self._refcnts.total() == 0

    _done_states = frozenset([TaskState.RESULTED, TaskState.CANCELLED, TaskState.EXCEPTED])

    def done(self) -> bool:
        """Return True if the task is done.

        A task that is "done" either:

        * Completed normally,
        * Was cancelled by another task, or
        * Raised an exception.
        """
        return self._state in self._done_states

    def result(self) -> Any:
        """Return the task's result, or raise an exception.

        Returns:
            If the task ran to completion, return its result.

        Raises:
            CancelledError: If the task was cancelled.
            Exception: If the task raise any other type of exception.
            TaskStateError: If the task is not done.
        """
        if self._state is TaskState.RESULTED:
            assert self._exception is None
            return self._result
        if self._state is TaskState.CANCELLED:
            assert isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state is TaskState.EXCEPTED:
            assert isinstance(self._exception, Exception)
            raise self._exception
        raise TaskStateError("Task is not done")

    def exception(self) -> Exception | None:
        """Return the task's exception.

        Returns:
            If the task raised an exception, return it.
            Otherwise, return None.

        Raises:
            If the task was cancelled, re-raise the CancelledError.
        """
        if self._state is TaskState.RESULTED:
            assert self._exception is None
            return self._exception
        if self._state is TaskState.CANCELLED:
            assert isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state is TaskState.EXCEPTED:
            assert isinstance(self._exception, Exception)
            return self._exception
        raise TaskStateError("Task is not done")

    def cancel(self, *args) -> bool:
        """Schedule task for cancellation.

        If a task is already done: return False.

        If a task is pending or waiting:

        1. Renege from all queues
        2. Reschedule to raise CancelledError in the current time slot
        3. Return True

        If a task is running, immediately raise CancelledError.

        Args:
            args: Arguments passed to CancelledError instance

        Returns:
            bool success indicator

        Raises:
            CancelledError: If the task cancels itself
        """
        # Already done; do nothing
        if self._cancelling or self.done():
            return False

        exc = CancelledError(*args)

        # Task is cancelling itself. Weird, but legal.
        if self is self._loop.task():
            raise exc

        # Pending/Waiting tasks must first renege from queues
        self._renege()

        # Reschedule for cancellation
        self._cancelling = True
        self._loop.call_soon(self, value=(TaskCommand.CANCEL, exc))

        # Success
        return True


class TaskGroup(LoopIf):
    """Group of tasks."""

    def __init__(self):
        self._parent = self._loop.task()

        # Tasks started in the with block
        self._setup_done = False
        self._setup_tasks: set[Task] = set()

        # Tasks in running/waiting/cancelling/pending state
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
        # Cancel children; suppress exceptions
        if exc:
            self._cancel_awaited()
            while self._awaited:
                child: Task = await self._loop.switch_coro()
                self._awaited.remove(child)

            # Re-raise parent exception
            return False

        # Parent did NOT raise an exception:
        # Await children; collect exceptions
        child_excs: list[Exception] = []
        while self._awaited:
            child: Task = await self._loop.switch_coro()
            self._awaited.remove(child)
            if child.state() is TaskState.EXCEPTED:
                assert child._exception is not None
                child_excs.append(child._exception)
                self._cancel_awaited()

        # Re-raise child exceptions
        if child_excs:
            raise ExceptionGroup("Child task(s) raised exception(s)", child_excs)

    def _cancel_awaited(self):
        for child in self._awaited:
            child.cancel()

    def create_task(
        self,
        coro: TaskCoro,
        name: str | None = None,
        priority: int = 0,
    ) -> Task:
        child = self._loop.create_task(coro, name, priority)
        child._group = self
        if self._setup_done:
            self._awaited.add(child)
            child._wait(self._parent)
        else:
            self._setup_tasks.add(child)
        return child
