"""Simulation using async/await.

We are intentionally imitating the style of Python's Event Loop API:
https://docs.python.org/3/library/asyncio-eventloop.html

Credit to David Beazley's "Build Your Own Async" tutorial for inspiration:
https://www.youtube.com/watch?v=Y4Gt3Xjd7G8
"""

from collections.abc import Callable, Coroutine, Generator
from enum import IntEnum, auto
from typing import Any

from ._error import FinishError, InvalidStateError
from ._suspend_resume import SuspendResume
from ._task import Task, TaskState
from ._taskq import TaskQueue
from ._variable import Variable

type Predicate = Callable[[], bool]


class LoopState(IntEnum):
    """Loop state."""

    # Initialized
    INIT = auto()

    # Currently running
    RUNNING = auto()

    # Halted by run limit
    HALTED = auto()

    # Done: all tasks completed
    COMPLETED = auto()

    # Done: finish() called
    FINISHED = auto()


class Loop:
    """Simulation event loop."""

    init_time = -1
    start_time = 0

    def __init__(self):
        """Initialize simulation."""
        self._state = LoopState.INIT

        # Simulation time
        self._time: int = self.init_time

        # Task queue
        self._queue = TaskQueue()

        # Currently executing task
        self._task: Task | None = None

        # State waiting set
        self._touched: set[Variable] = set()

    def time(self) -> int:
        return self._time

    def task(self) -> Task:
        assert self._task is not None
        return self._task

    # def done(self) -> bool:
    #    return self._state in {LoopState.COMPLETED, LoopState.FINISHED}

    # Scheduling methods
    def _schedule(self, time: int, task: Task, value):
        task.set_state(TaskState.PENDING)
        self._queue.push(time, task, value)

    def call_soon(self, task: Task, value=None):
        self._schedule(self._time, task, value)

    def call_later(self, delay: int, task: Task, value=None):
        self._schedule(self._time + delay, task, value)

    def call_at(self, when: int, task: Task, value=None):
        self._schedule(when, task, value)

    # Task await / done callbacks
    def _task_run(self, task: Task, value):
        task.set_state(TaskState.RUNNING)
        task.coro.send(value)

    def _task_return(self, task: Task, e: StopIteration):
        task.set_state(TaskState.RETURNED)
        task.set_result(e.value)

    # Model touch / update callbacks
    def model_touch(self, v: Variable):
        self._touched.add(v)

    def _model_update(self):
        while self._touched:
            v = self._touched.pop()
            v.update()

    def _limit(self, ticks: int | None, until: int | None) -> int | None:
        """Determine the run limit."""
        match ticks, until:
            # Run until no tasks left
            case None, None:
                return None
            # Run until an absolute time
            case None, int():
                return until
            # Run until a number of ticks in the future
            case int(), None:
                return max(self.start_time, self._time) + ticks
            case _:
                s = "Expected either ticks or until to be int | None"
                raise TypeError(s)

    def _run_kernel(self, limit: int | None):
        if self._state not in {LoopState.INIT, LoopState.HALTED}:
            raise InvalidStateError("WTF")

        self._state = LoopState.RUNNING

        while self._queue:
            # Peek when next event is scheduled
            time, _, _ = self._queue.peek()

            # Protect against time traveling tasks
            assert time > self._time

            # Exit if we hit the run limit
            if limit is not None and time >= limit:
                self._state = LoopState.HALTED
                return

            # Otherwise, advance to new timeslot
            self._time = time

            # Execute time slot
            for _, task, value in self._queue.pop_time():
                self._task = task
                try:
                    self._task_run(task, value)
                except StopIteration as e:
                    self._task_return(task, e)

            self._model_update()
        else:
            self._state = LoopState.COMPLETED

    def run(self, ticks: int | None = None, until: int | None = None):
        """Run the simulation.

        Until:
        1. We hit the runlimit, OR
        2. There are no tasks left in the queue
        """
        limit = self._limit(ticks, until)

        # Run until either 1) all tasks complete, or 2) finish()
        try:
            self._run_kernel(limit)
        except FinishError:
            self._state = LoopState.FINISHED

    def _iter_kernel(self) -> Generator[int, None, None]:
        self._state = LoopState.RUNNING

        while self._queue:
            # Peek when next event is scheduled
            time, _, _ = self._queue.peek()

            # Protect against time traveling tasks
            assert time > self._time

            # Otherwise, advance to new timeslot
            self._time = time

            yield self._time

            # Execute time slot
            for _, task, value in self._queue.pop_time():
                self._task = task
                try:
                    self._task_run(task, value)
                except StopIteration as e:
                    self._task_return(task, e)

            self._model_update()
        else:
            self._state = LoopState.COMPLETED

    def irun(self) -> Generator[int, None, None]:
        """Iterate the simulation.

        Until:
        1. We hit the runlimit, OR
        2. There are no tasks left in the queue
        """
        try:
            yield from self._iter_kernel()
        except FinishError:
            self._state = LoopState.FINISHED


_loop: Loop | None = None


def get_running_loop() -> Loop:
    """Get the currently running loop."""
    if _loop is None:
        raise RuntimeError("No running loop")
    return _loop


def get_loop() -> Loop | None:
    """Get the current loop."""
    return _loop


def set_loop(loop: Loop | None):
    """Set the current loop."""
    global _loop
    _loop = loop


def now() -> int:
    if _loop is None:
        raise RuntimeError("No running loop")
    return _loop.time()


def create_task(coro: Coroutine[Any, Any, Any], region: int = 0) -> Task:
    loop = get_running_loop()
    task = Task(coro, region)
    loop.call_soon(task)
    return task


def run(
    coro: Coroutine[Any, Any, Any] | None = None,
    region: int = 0,
    loop: Loop | None = None,
    ticks: int | None = None,
    until: int | None = None,
):
    """Run a simulation."""
    global _loop

    task = None
    if loop is not None:
        _loop = loop
    else:
        _loop = Loop()
        assert coro is not None
        task = Task(coro, region)
        _loop.call_at(Loop.start_time, task)

    _loop.run(ticks, until)


def irun(
    coro: Coroutine[Any, Any, Any] | None = None,
    region: int = 0,
    loop: Loop | None = None,
) -> Generator[int, None, None]:
    """Iterate a simulation."""
    global _loop

    task = None
    if loop is not None:
        _loop = loop
    else:
        _loop = Loop()
        assert coro is not None
        task = Task(coro, region)
        _loop.call_at(Loop.start_time, task)

    yield from _loop.irun()


async def sleep(delay: int):
    """Suspend the task, and wake up after a delay."""
    loop = get_running_loop()
    loop.call_later(delay, loop.task())
    await SuspendResume()


async def model_wait(*vps: tuple[Variable, Predicate | None]) -> Variable:
    loop = get_running_loop()
    task = loop.task()

    for v, p in vps:
        v.add_task(task, p)
        task.add_parent(v)

    # Suspend
    task.set_state(TaskState.WAITING)
    v = await SuspendResume()

    # Resume
    task.remove_parent(v)
    return v


def finish():
    raise FinishError()
