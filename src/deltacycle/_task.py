"""Task: coroutine wrapper"""

from __future__ import annotations

import logging
from abc import ABC
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Coroutine, Generator
from enum import IntEnum, auto
from functools import cached_property
from typing import Any

from ._loop_if import LoopIf

logger = logging.getLogger("deltacycle")

type Predicate = Callable[[], bool]


class CancelledError(Exception):
    """Task has been cancelled."""


class InvalidStateError(Exception):
    """Task has an invalid state."""


class TaskState(IntEnum):
    """Task State

    Transitions::

                   +---------------------+
                   |                     |
                   v                     |
        INIT -> PENDING -> RUNNING -> WAITING
                                   -> COMPLETE
                                   -> CANCELLED
                                   -> EXCEPTED
    """

    # Initialized
    INIT = auto()

    # In the event queue
    PENDING = auto()

    # Suspended; Waiting for:
    # * Event set
    # * Semaphore release
    # * Task done
    WAITING = auto()

    # Dropped from PENDING/WAITING
    CANCELLING = auto()

    # Currently running
    RUNNING = auto()

    # Done: returned a result
    COMPLETE = auto()
    # Done: cancelled
    CANCELLED = auto()
    # Done: raised an exception
    EXCEPTED = auto()


_task_state_transitions = {
    TaskState.INIT: {TaskState.PENDING},
    TaskState.PENDING: {TaskState.CANCELLING, TaskState.RUNNING},
    TaskState.WAITING: {TaskState.CANCELLING, TaskState.PENDING},
    TaskState.CANCELLING: {TaskState.PENDING},
    TaskState.RUNNING: {
        TaskState.PENDING,  # sleep
        TaskState.WAITING,  # suspend/resume
        TaskState.COMPLETE,
        TaskState.CANCELLED,
        TaskState.EXCEPTED,
    },
}


class HoldIf(ABC):
    def __bool__(self) -> bool:
        raise NotImplementedError()  # pragma: no cover

    def drop(self, task: Task):
        raise NotImplementedError()  # pragma: no cover

    def pop(self) -> Task:
        raise NotImplementedError()  # pragma: no cover


class WaitFifo(HoldIf):
    """Initiator type; tasks wait in FIFO order."""

    def __init__(self):
        self._tasks: deque[Task] = deque()

    def __bool__(self) -> bool:
        return bool(self._tasks)

    def drop(self, task: Task):
        self._tasks.remove(task)

    def push(self, task: Task):
        task._holding.add(self)
        self._tasks.append(task)

    def pop(self) -> Task:
        task = self._tasks.popleft()
        task._holding.remove(self)
        return task


class WaitTouch(HoldIf):
    """Initiator type; tasks wait for variable touch."""

    def __init__(self):
        self._tasks: dict[Task, Predicate] = dict()
        self._predicated: set[Task] = set()

    def __bool__(self) -> bool:
        return bool(self._predicated)

    def drop(self, task: Task):
        del self._tasks[task]

    def push(self, task: Task, p: Predicate):
        task._holding.add(self)
        self._tasks[task] = p

    def touch(self):
        self._predicated = {task for task, p in self._tasks.items() if p()}

    def pop(self) -> Task:
        task = self._predicated.pop()
        while task._holding:
            task._holding.pop().drop(task)
        return task


class Task(Awaitable[Any], LoopIf):
    """Coroutine wrapper."""

    def __init__(
        self,
        coro: Coroutine[Any, Any, Any],
        parent: Task | None,
        name: str | None = None,
        priority: int = 0,
    ):
        self._state = TaskState.INIT

        self._coro = coro
        self._parent = parent
        self._children = Counter()

        if parent is None:
            assert name is not None
            self._name = name
        else:
            index = parent._children[name]
            parent._children[name] += 1
            if name is None:
                self._name = f"{index}"
            else:
                self._name = f"{name}.{index}"

        self._priority = priority

        # Containers holding a reference to this task
        self._holding: set[HoldIf] = set()

        # Other tasks waiting for this task to complete
        self._waiting = WaitFifo()

        # Completion
        self._result: Any = None

        # Exception
        self._exception: Exception | None = None

    def __await__(self) -> Generator[None, None, Any]:
        if not self.done():
            task = self._loop.task()
            self._waiting.push(task)
            task._set_state(TaskState.WAITING)
            # Suspend
            yield

        # Resume
        return self.result()

    @property
    def coro(self) -> Coroutine[Any, Any, Any]:
        return self._coro

    @property
    def parent(self) -> Task | None:
        return self._parent

    @property
    def name(self) -> str:
        return self._name

    @cached_property
    def qualname(self) -> str:
        if self._parent is None:
            return f"/{self._name}"
        return f"{self._parent.qualname}/{self._name}"

    @property
    def priority(self) -> int:
        return self._priority

    def _set_state(self, state: TaskState):
        assert state in _task_state_transitions[self._state]
        logger.debug("Task %s: %s => %s", self.qualname, self._state.name, state.name)
        self._state = state

    def state(self) -> TaskState:
        return self._state

    def _do_run(self, value: Any = None):
        self._set_state(TaskState.RUNNING)
        if self._exception is None:
            self._coro.send(value)
        else:
            self._coro.throw(self._exception)

    def _do_complete(self, e: StopIteration):
        while self._waiting:
            self._loop.call_soon(self._waiting.pop(), value=self)
        self._set_result(e.value)
        self._set_state(TaskState.COMPLETE)

    def _do_cancel(self, e: CancelledError):
        while self._waiting:
            self._loop.call_soon(self._waiting.pop(), value=self)
        self._set_exception(e)
        self._set_state(TaskState.CANCELLED)

    def _do_except(self, e: Exception):
        while self._waiting:
            self._loop.call_soon(self._waiting.pop(), value=self)
        self._set_exception(e)
        self._set_state(TaskState.EXCEPTED)

    def done(self) -> bool:
        """Return True if the task is done.

        A task that is "done" either 1) completed normally,
        2) was cancelled by another task, or 3) raised an exception.
        """
        return self._state in {
            TaskState.COMPLETE,
            TaskState.CANCELLED,
            TaskState.EXCEPTED,
        }

    def cancelled(self) -> bool:
        """Return True if the task was cancelled."""
        return self._state == TaskState.CANCELLED

    def _set_result(self, result: Any):
        if self.done():
            raise InvalidStateError("Task is already done")
        self._result = result

    def result(self) -> Any:
        """Return the task's result, or raise an exception.

        Returns:
            If the task ran to completion, return its result.

        Raises:
            CancelledError: If the task was cancelled.
            Exception: If the task raise any other type of exception.
            InvalidStateError: If the task is not done.
        """
        if self._state == TaskState.COMPLETE:
            assert self._exception is None
            return self._result
        if self._state == TaskState.CANCELLED:
            assert isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state == TaskState.EXCEPTED:
            assert isinstance(self._exception, Exception)
            raise self._exception
        raise InvalidStateError("Task is not done")

    def _set_exception(self, e: Exception):
        if self.done():
            raise InvalidStateError("Task is already done")
        self._exception = e

    def exception(self) -> Exception | None:
        if self._state == TaskState.COMPLETE:
            assert self._exception is None
            return self._exception
        if self._state == TaskState.CANCELLED:
            assert isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state == TaskState.EXCEPTED:
            assert isinstance(self._exception, Exception)
            return self._exception
        raise InvalidStateError("Task is not done")

    def _renege(self):
        while self._holding:
            q = self._holding.pop()
            q.drop(self)

    def cancel(self, msg: str | None = None) -> bool:
        """Schedule task for cancellation.

        If a task is already done: return False.

        If a task is pending or waiting:

        1. Renege from all queues
        2. Reschedule to raise CancelledError in the current time slot
        3. Return True

        If a task is running, immediately raise CancelledError.

        Args:
            msg: Optional str message passed to CancelledError instance

        Returns:
            bool success indicator

        Raises:
            CancelledError: If the task cancels itself
        """
        # A normal task would be scheduled immediately.
        # Something went wrong here.
        assert self._state not in {TaskState.INIT, TaskState.CANCELLING}

        # Already done; do nothing
        if self.done():
            return False

        args = () if msg is None else (msg,)
        exc = CancelledError(*args)

        # Task is cancelling itself. Weird, but legal.
        if self._state is TaskState.RUNNING:
            raise exc

        # Pending/Waiting tasks must first renege from queues
        if self._state is TaskState.PENDING:
            self._loop._queue.drop(self)
        elif self._state is TaskState.WAITING:
            self._renege()
        else:
            assert False  # pragma: no cover

        # Reschedule for cancellation
        self._set_state(TaskState.CANCELLING)
        self._set_exception(exc)
        self._loop.call_soon(self)

        return True
