"""Task: coroutine wrapper"""

from __future__ import annotations

import heapq
import logging
from abc import ABC
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Coroutine, Generator
from enum import IntEnum, auto
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

        INIT -> RUNNING -> COMPLETE
                        -> CANCELLED
                        -> EXCEPTED
    """

    # Initialized
    INIT = auto()

    # Currently running
    RUNNING = auto()

    # Done: returned a result
    COMPLETE = auto()
    # Done: cancelled
    CANCELLED = auto()
    # Done: raised an exception
    EXCEPTED = auto()


_task_state_transitions = {
    TaskState.INIT: {TaskState.RUNNING},
    TaskState.RUNNING: {
        TaskState.COMPLETE,
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

    def drop(self, task: Task):
        for i, (_, _, _, t, _) in enumerate(self._items):
            if t is task:
                index = i
                break
        else:
            assert False  # pragma: no cover
        self._items.pop(index)

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
        item._link(self)
        self._items.append(item)

    def pop(self) -> Task:
        task = self._items.popleft()
        task._unlink(self)
        return task

    def drop(self, task: Task):
        self._items.remove(task)


class WaitTouch(TaskQueueIf):
    """Tasks wait for variable touch."""

    def __init__(self):
        self._items: deque[Task] = deque()
        self._tps: dict[Task, Predicate] = dict()

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[Predicate, Task]):
        p, task = item
        task._link(self)
        self._tps[task] = p

    def pop(self) -> Task:
        task = self._items.popleft()
        task._unlink(self)
        return task

    def drop(self, task: Task):
        del self._tps[task]

    def touch(self):
        assert not self._items
        for task, p in self._tps.items():
            if p():
                self._items.append(task)


class Task(Awaitable[Any], LoopIf):
    """Coroutine wrapper."""

    _index = 0

    def __init__(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
        priority: int = 0,
    ):
        self._state = TaskState.INIT

        self._coro = coro
        if name is None:
            self._name = f"Task-{self.__class__._index}"
            self.__class__._index += 1
        else:
            self._name = name
        self._priority = priority

        # Reference counts for this task
        self._refcnts: Counter[TaskQueueIf] = Counter()

        # Other tasks waiting for this task to complete
        self._waiting = WaitFifo()

        # Completion
        self._result: Any = None

        # Exception
        self._exception: Exception | None = None

    def __await__(self) -> Generator[None, Task, Any]:
        if not self.done():
            task = self._loop.task()
            self._waiting.push(task)
            t: Task = yield from self._loop.switch_gen()
            assert t is self

        # Resume
        return self.result()

    def _wait(self, task: Task):
        self._waiting.push(task)

    def _set(self):
        while self._waiting:
            task = self._waiting.pop()
            self._loop.call_soon(task, value=self)

    @property
    def coro(self) -> Coroutine[Any, Any, Any]:
        return self._coro

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

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
        while self._refcnts:
            tq, cnt = self._refcnts.popitem()
            for _ in range(cnt):
                tq.drop(self)

    def _do_run(self, value: Any = None):
        if self._state is TaskState.INIT:
            self._set_state(TaskState.RUNNING)
        elif self._state is not TaskState.RUNNING:
            assert False  # pragma: no cover

        # Start / Resume coroutine
        if self._exception is None:
            self._coro.send(value)
        else:
            self._coro.throw(self._exception)

    def _do_complete(self, exc: StopIteration):
        self._set_result(exc.value)
        self._set_state(TaskState.COMPLETE)
        self._set()

    def _do_cancel(self, exc: CancelledError):
        self._set_exception(exc)
        self._set_state(TaskState.CANCELLED)
        self._set()

    def _do_except(self, exc: Exception):
        self._set_exception(exc)
        self._set_state(TaskState.EXCEPTED)
        self._set()

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
        return self._state is TaskState.CANCELLED

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
        if self._state is TaskState.COMPLETE:
            assert self._exception is None
            return self._result
        if self._state is TaskState.CANCELLED:
            assert isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state is TaskState.EXCEPTED:
            assert isinstance(self._exception, Exception)
            raise self._exception
        raise InvalidStateError("Task is not done")

    def _set_exception(self, exc: Exception):
        if self.done():
            raise InvalidStateError("Task is already done")
        self._exception = exc

    def exception(self) -> Exception | None:
        """Return the task's exception.

        Returns:
            If the task raised an exception, return it.
            Otherwise, return None.

        Raises:
            If the task was cancelled, re-raise the CancelledError.
        """
        if self._state is TaskState.COMPLETE:
            assert self._exception is None
            return self._exception
        if self._state is TaskState.CANCELLED:
            assert isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state is TaskState.EXCEPTED:
            assert isinstance(self._exception, Exception)
            return self._exception
        raise InvalidStateError("Task is not done")

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
        # Already done; do nothing
        if self.done():
            return False

        args = () if msg is None else (msg,)
        exc = CancelledError(*args)

        # Task is cancelling itself. Weird, but legal.
        if self is self._loop.task():
            raise exc

        # Pending/Waiting tasks must first renege from queues
        self._renege()

        # Reschedule for cancellation
        self._set_exception(exc)
        self._loop.call_soon(self)

        return True
