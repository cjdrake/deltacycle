"""Task: coroutine wrapper"""

# pylint: disable=protected-access

from __future__ import annotations

from abc import ABC
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine, Generator
from enum import IntEnum, auto
from typing import Any

from ._error import CancelledError, InvalidStateError
from ._loop_if import LoopIf

type Predicate = Callable[[], bool]


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


class WaitIf(ABC):
    def __bool__(self) -> bool:
        raise NotImplementedError()  # pragma: no cover

    def drop(self, task: Task):
        raise NotImplementedError()  # pragma: no cover


class WaitFifo(WaitIf):
    """Initiator type; tasks wait in FIFO order."""

    def __init__(self):
        self._tasks: deque[Task] = deque()

    def __bool__(self) -> bool:
        return bool(self._tasks)

    def drop(self, task: Task):
        self._tasks.remove(task)

    def push(self, task: Task):
        task._waitqs.add(self)
        self._tasks.append(task)

    def pop(self) -> Task:
        task = self._tasks.popleft()
        task._waitqs.remove(self)
        return task

    def pop_all(self) -> Generator[Task, None, None]:
        while self._tasks:
            yield self.pop()


class WaitTouch(WaitIf):
    """Initiator type; tasks wait for variable touch."""

    def __init__(self):
        self._tasks: set[Task] = set()
        self._preds: dict[Task, Predicate] = dict()

    def __bool__(self) -> bool:
        return bool(self._tasks)

    def drop(self, task: Task):
        self._tasks.remove(task)
        del self._preds[task]

    def push(self, task: Task, pred: Predicate):
        task._waitqs.add(self)
        self._tasks.add(task)
        self._preds[task] = pred

    def pop_predicated(self) -> Generator[Task, None, None]:
        tasks = {task for task in self._tasks if self._preds[task]()}
        while tasks:
            task = tasks.pop()
            task._renege()
            yield task


class Task(Awaitable, LoopIf):
    """Coroutine wrapper."""

    def __init__(self, coro: Coroutine[Any, Any, Any], region: int = 0):
        self._coro = coro
        self._region = region
        self._state = TaskState.INIT

        self._waitqs: set[WaitIf] = set()
        self._task_fifo = WaitFifo()

        # Completion
        self._result: Any = None

        # Exception
        self._exception: Exception | None = None

    def __await__(self) -> Generator[None, None, Any]:
        if not self.done():
            task = self._loop.task()
            self._task_fifo.push(task)
            task.set_state(TaskState.WAITING)
            # Suspend
            yield

        # Resume
        return self.result()

    @property
    def coro(self) -> Coroutine[Any, Any, Any]:
        return self._coro

    @property
    def region(self) -> int:
        return self._region

    def set_state(self, state: TaskState):
        match self._state:
            case TaskState.INIT:
                assert state is TaskState.PENDING
            case TaskState.PENDING:
                assert state in {TaskState.CANCELLING, TaskState.RUNNING}
            case TaskState.WAITING:
                assert state in {TaskState.CANCELLING, TaskState.PENDING}
            case TaskState.CANCELLING:
                assert state is TaskState.PENDING
            case TaskState.RUNNING:
                assert state in {
                    TaskState.PENDING,  # sleep
                    TaskState.WAITING,  # suspend/resume
                    TaskState.COMPLETE,
                    TaskState.CANCELLED,
                    TaskState.EXCEPTED,
                }
            case _:  # pragma: no cover
                assert False
        self._state = state

    def state(self) -> TaskState:
        return self._state

    def _renege(self):
        while self._waitqs:
            waitq = self._waitqs.pop()
            waitq.drop(self)

    def do_run(self, value: Any = None):
        self.set_state(TaskState.RUNNING)
        if self._exception is None:
            self._coro.send(value)
        else:
            self._coro.throw(self._exception)

    def do_complete(self, e: StopIteration):
        for task in self._task_fifo.pop_all():
            self._loop.call_soon(task, value=self)
        self.set_result(e.value)
        self.set_state(TaskState.COMPLETE)

    def do_cancel(self, e: CancelledError):
        for task in self._task_fifo.pop_all():
            self._loop.call_soon(task, value=self)
        self.set_exception(e)
        self.set_state(TaskState.CANCELLED)

    def do_except(self, e: Exception):
        for task in self._task_fifo.pop_all():
            self._loop.call_soon(task, value=self)
        self.set_exception(e)
        self.set_state(TaskState.EXCEPTED)

    def done(self) -> bool:
        return self._state in {
            TaskState.COMPLETE,
            TaskState.CANCELLED,
            TaskState.EXCEPTED,
        }

    def cancelled(self) -> bool:
        return self._state == TaskState.CANCELLED

    def set_result(self, result: Any):
        if self.done():
            raise InvalidStateError("Task is already done")
        self._result = result

    def result(self) -> Any:
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

    def set_exception(self, e: Exception):
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

    def cancel(self, msg: str | None = None):
        match self._state:
            case TaskState.WAITING:
                self.set_state(TaskState.CANCELLING)
                self._renege()
            case TaskState.PENDING:
                self.set_state(TaskState.CANCELLING)
                # Drop task from loop queue
                self._loop.drop_task(self)
            case _:
                # TODO(cjdrake): Is this the correct error?
                raise ValueError("Task is not WAITING or PENDING")

        args = () if msg is None else (msg,)
        exc = CancelledError(*args)
        self.set_exception(exc)
        self._loop.call_soon(self)
