"""Simulation using async/await.

We are intentionally imitating the style of Python's Event Loop API:
https://docs.python.org/3/library/asyncio-eventloop.html

Credit to David Beazley's "Build Your Own Async" tutorial for inspiration:
https://www.youtube.com/watch?v=Y4Gt3Xjd7G8
"""

from __future__ import annotations

import heapq
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Coroutine, Generator
from enum import IntEnum, auto
from typing import Any

from ._error import CancelledError, FinishError, InvalidStateError
from ._event import Event
from ._semaphore import Semaphore
from ._suspend_resume import SuspendResume
from ._variable import Variable

type Predicate = Callable[[], bool]


class TaskState(IntEnum):
    """Task State.

    Transitions::

                   +-----------------------+
                   |                       |
                   v                       |
        INIT -> PENDING -> RUNNING -> WAIT_*
                                   -> CANCELLED
                                   -> EXCEPTED
                                   -> RETURNED
    """

    # Default value after instantiation
    INIT = auto()

    # Awaiting task/event/semaphore in FIFO order
    WAIT_FIFO = auto()

    # Awaiting model touch
    WAIT_STATE = auto()

    # In the event queue
    PENDING = auto()

    # Current running
    RUNNING = auto()

    # Done: returned a result
    RETURNED = auto()
    # Done: raised an exception
    EXCEPTED = auto()
    # Done: cancelled
    CANCELLED = auto()


class Task(Awaitable):
    """Coroutine wrapper."""

    def __init__(self, coro: Coroutine[Any, Any, Any], region: int = 0):
        self._coro = coro
        self._region = region

        self._state = TaskState.INIT
        self._parent: Task | Event | Semaphore | Variable | None = None

        self._result: Any = None

        # Set flag to throw exception
        self._exc_flag = False
        self._exception = None

    def __await__(self) -> Generator[None, None, None]:
        loop = get_running_loop()

        if not self.done():
            loop.fifo_wait(self)
            # Suspend
            yield

        # Resume
        return

    @property
    def coro(self) -> Coroutine[Any, Any, Any]:
        return self._coro

    @property
    def region(self) -> int:
        return self._region

    def set_state(self, state: TaskState, parent=None):
        self._state = state
        self._parent = parent

    def run(self, value: Any = None):
        self._state = TaskState.RUNNING
        if self._exc_flag:
            self._exc_flag = False
            assert self._exception is not None
            self._coro.throw(self._exception)
        else:
            self._coro.send(value)

    def done(self) -> bool:
        return self._state in {
            TaskState.CANCELLED,
            TaskState.EXCEPTED,
            TaskState.RETURNED,
        }

    def cancelled(self) -> bool:
        return self._state == TaskState.CANCELLED

    def set_result(self, result):
        self._result = result

    def result(self) -> Any:
        if self._state == TaskState.CANCELLED:
            assert self._exception is not None and isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state == TaskState.EXCEPTED:
            assert self._exception is not None
            raise self._exception  # Re-raise exception
        if self._state == TaskState.RETURNED:
            assert self._exception is None
            return self._result
        raise InvalidStateError("Task is not done")

    def set_exception(self, exc):
        self._exc_flag = True
        self._exception = exc

    def exception(self):
        if self._state == TaskState.CANCELLED:
            assert self._exception is not None and isinstance(self._exception, CancelledError)
            raise self._exception
        if self._state == TaskState.EXCEPTED:
            assert self._exception is not None
            return self._exception  # Return exception
        if self._state == TaskState.RETURNED:
            assert self._exception is None
            return self._exception
        raise InvalidStateError("Task is not done")

    def cancel(self, msg: str | None = None):
        loop = get_running_loop()

        match self._state:
            case TaskState.WAIT_FIFO:
                assert isinstance(self._parent, (Task, Event, Semaphore))
                loop.fifo_drop(self._parent, self)
            case TaskState.WAIT_STATE:
                assert isinstance(self._parent, Variable)
                loop.state_drop(self._parent, self)
            case TaskState.PENDING:
                loop.drop(self)
            case _:
                raise ValueError("Task is not WAITING or PENDING")

        args = () if msg is None else (msg,)
        exc = CancelledError(*args)
        self.set_exception(exc)
        loop.call_soon(self)


def create_task(coro: Coroutine[Any, Any, Any], region: int = 0) -> Task:
    loop = get_running_loop()
    return loop.task_create(coro, region)


class TaskGroup:
    """Group of tasks."""

    def __init__(self):
        self._tasks = deque()

    def create_task(self, coro: Coroutine[Any, Any, Any], region: int = 0) -> Task:
        loop = get_running_loop()
        task = loop.task_create(coro, region)
        self._tasks.append(task)
        return task

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        while self._tasks:
            task = self._tasks.popleft()
            await task


type _TaskQueueItem = tuple[int, Task, Any]


class _TaskQueue:
    """Priority queue for ordering task execution."""

    def __init__(self):
        # time, region, index, task, value
        self._items: list[tuple[int, int, int, Task, Any]] = []

        # Monotonically increasing integer
        # Breaks (time, region, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def clear(self):
        self._items.clear()
        self._index = 0

    def push(self, time: int, task: Task, value: Any = None):
        item = (time, task.region, self._index, task, value)
        heapq.heappush(self._items, item)
        self._index += 1

    def peek(self) -> _TaskQueueItem:
        time, _, _, task, value = self._items[0]
        return (time, task, value)

    def pop(self) -> _TaskQueueItem:
        time, _, _, task, value = heapq.heappop(self._items)
        return (time, task, value)

    def pop_time(self) -> Generator[_TaskQueueItem, None, None]:
        time, _, _, task, value = heapq.heappop(self._items)
        yield (time, task, value)
        while self._items and self._items[0][0] == time:
            _, _, _, task, value = heapq.heappop(self._items)
            yield (time, task, value)

    def drop(self, task: Task):
        for i, (_, _, _, t, _) in enumerate(self._items):
            if t is task:
                index = i
                break
        else:
            raise ValueError("Task is not scheduled")
        self._items.pop(index)


class Loop:
    """Simulation event loop."""

    init_time = -1
    start_time = 0

    def __init__(self):
        """Initialize simulation."""
        # Simulation time
        self._time: int = self.init_time

        # Task queue
        self._queue = _TaskQueue()

        # Currently executing task
        self._task: Task | None = None

        # Awaitable FIFOs
        self._wait_fifos: dict[Task | Event | Semaphore, deque[Task]] = defaultdict(deque)

        # Variable waiting set
        self._waiting: dict[Variable, set[Task]] = defaultdict(set)
        self._predicates: dict[Variable, dict[Task, Predicate]] = defaultdict(dict)
        self._touched: set[Variable] = set()

    def clear(self):
        """Clear all task collections."""
        self._queue.clear()
        self._wait_fifos.clear()
        self._waiting.clear()
        self._predicates.clear()
        self._touched.clear()

    def restart(self):
        """Restart current simulation."""
        self._time = self.init_time
        self._task = None
        self.clear()

    def time(self) -> int:
        return self._time

    def task(self) -> Task:
        assert self._task is not None
        return self._task

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

    def drop(self, task: Task):
        self._queue.drop(task)

    def fifo_wait(self, aw: Task | Event | Semaphore):
        task = self.task()
        task.set_state(TaskState.WAIT_FIFO, aw)
        self._wait_fifos[aw].append(task)

    def fifo_drop(self, aw: Task | Event | Semaphore, task: Task):
        self._wait_fifos[aw].remove(task)

    # Task await / done callbacks
    def task_create(self, coro: Coroutine[Any, Any, Any], region: int = 0) -> Task:
        # Cannot call task_create before the simulation starts
        assert self._time >= 0
        task = Task(coro, region)
        self.call_soon(task)
        return task

    def _task_return(self, ptask: Task, e: StopIteration):
        waiting = self._wait_fifos[ptask]
        while waiting:
            ctask = waiting.popleft()
            self.call_soon(ctask, value=ptask)
        ptask.set_state(TaskState.RETURNED)
        ptask.set_result(e.value)

    def _task_cancel(self, ptask: Task, e: CancelledError):
        waiting = self._wait_fifos[ptask]
        while waiting:
            ctask = waiting.popleft()
            ctask.set_exception(e)
            self.call_soon(ctask, value=ptask)
        ptask.set_state(TaskState.CANCELLED)

    def _task_except(self, ptask: Task, e: Exception):
        waiting = self._wait_fifos[ptask]
        while waiting:
            ctask = waiting.popleft()
            ctask.set_exception(e)
            self.call_soon(ctask, value=ptask)
        ptask.set_state(TaskState.EXCEPTED)

    # Event wait / set callbacks
    def event_set(self, event: Event):
        waiting = self._wait_fifos[event]
        while waiting:
            task = waiting.popleft()
            self.call_soon(task, value=event)

    # Semaphore acquire / release callbacks
    def sem_release(self, sem: Semaphore) -> bool:
        waiting = self._wait_fifos[sem]
        if waiting:
            task = waiting.popleft()
            self.call_soon(task, value=sem)
            # Do NOT increment semaphore counter
            return False
        # Increment semaphore counter
        return True

    # Model suspend / resume callbacks
    def state_wait(self, x: Variable, p: Predicate):
        task = self.task()
        task.set_state(TaskState.WAIT_STATE, x)
        self._waiting[x].add(task)
        self._predicates[x][task] = p

    def state_drop(self, x: Variable, task: Task):
        self._waiting[x].remove(task)
        del self._predicates[x][task]

    def state_touch(self, x: Variable):
        waiting = self._waiting[x]
        predicates = self._predicates[x]
        pending = [task for task in waiting if predicates[task]()]
        for task in pending:
            self.state_drop(x, task)
            self.call_soon(task, value=x)
        # Add variable to update set
        self._touched.add(x)

    def _state_update(self):
        while self._touched:
            x = self._touched.pop()
            x.update()

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
        while self._queue:
            # Peek when next event is scheduled
            time, _, _ = self._queue.peek()

            # Protect against time traveling tasks
            assert time > self._time

            # Exit if we hit the run limit
            if limit is not None and time >= limit:
                break

            # Otherwise, advance to new timeslot
            self._time = time

            # Execute time slot
            for _, task, value in self._queue.pop_time():
                self._task = task
                try:
                    task.run(value)
                except StopIteration as e:
                    self._task_return(task, e)
                except CancelledError as e:
                    self._task_cancel(task, e)
                except Exception as e:
                    self._task_except(task, e)
                    raise

            # Update simulation state
            self._state_update()

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
            self.clear()

    def _iter_kernel(self, limit: int | None) -> Generator[int, None, None]:
        while self._queue:
            # Peek when next event is scheduled
            time, _, _ = self._queue.peek()

            # Protect against time traveling tasks
            assert time > self._time

            # Exit if we hit the run limit
            if limit is not None and time >= limit:
                return

            # Otherwise, advance to new timeslot
            self._time = time

            # Execute time slot
            for _, task, value in self._queue.pop_time():
                self._task = task
                try:
                    task.run(value)
                except StopIteration as e:
                    self._task_return(task, e)
                except CancelledError as e:
                    self._task_cancel(task, e)
                except Exception as e:
                    self._task_except(task, e)
                    raise

            # Update simulation state
            self._state_update()
            yield self._time

    def irun(
        self, ticks: int | None = None, until: int | None = None
    ) -> Generator[int, None, None]:
        """Iterate the simulation.

        Until:
        1. We hit the runlimit, OR
        2. There are no tasks left in the queue
        """
        limit = self._limit(ticks, until)

        try:
            yield from self._iter_kernel(limit)
        except FinishError:
            self.clear()


_loop: Loop | None = None


def get_running_loop() -> Loop:
    if _loop is None:
        raise RuntimeError("No running loop")
    return _loop


def get_loop() -> Loop | None:
    """Get the current event loop."""
    return _loop


def set_loop(loop: Loop):
    """Set the current event loop."""
    global _loop
    _loop = loop


def now() -> int:
    if _loop is None:
        raise RuntimeError("No running loop")
    return _loop.time()


def run(
    coro: Coroutine[Any, Any, Any] | None = None,
    region: int = 0,
    loop: Loop | None = None,
    ticks: int | None = None,
    until: int | None = None,
):
    """Run a simulation."""
    if loop is None:
        set_loop(loop := Loop())
        # TODO(cjdrake): Raise an exception for this
        assert coro is not None
        task = Task(coro, region)
        loop.call_at(Loop.start_time, task)
    else:
        set_loop(loop)

    loop.run(ticks, until)


def irun(
    coro: Coroutine[Any, Any, Any] | None = None,
    region: int = 0,
    loop: Loop | None = None,
    ticks: int | None = None,
    until: int | None = None,
) -> Generator[int, None, None]:
    """Iterate a simulation."""
    if loop is None:
        set_loop(loop := Loop())
        # TODO(cjdrake): Raise an exception for this
        assert coro is not None
        task = Task(coro, region)
        loop.call_at(Loop.start_time, task)
    else:
        set_loop(loop)

    yield from loop.irun(ticks, until)


async def sleep(delay: int):
    """Suspend the task, and wake up after a delay."""
    loop = get_running_loop()
    task = loop.task()
    loop.call_later(delay, task)
    await SuspendResume()


async def changed(*xs: Variable) -> Variable:
    """Resume execution upon state change."""
    loop = get_running_loop()
    for x in xs:
        loop.state_wait(x, x.changed)
    x = await SuspendResume()
    return x


async def resume(*triggers: tuple[Variable, Predicate]) -> Variable:
    """Resume execution upon event."""
    loop = get_running_loop()
    for x, p in triggers:
        loop.state_wait(x, p)
    x = await SuspendResume()
    return x


FIRST_COMPLETED = "FIRST_COMPLETED"
FIRST_EXCEPTION = "FIRST_EXCEPTION"
ALL_COMPLETED = "ALL_COMPLETED"


async def wait(aws, return_when=ALL_COMPLETED) -> tuple[set[Task], set[Task]]:
    loop = get_running_loop()

    # TODO(cjdrake): Catch exceptions
    if return_when == FIRST_EXCEPTION:
        raise NotImplementedError("FIRST_EXCEPTION not implemented yet")

    if return_when not in {FIRST_COMPLETED, ALL_COMPLETED}:
        exp = ", ".join([FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED])
        s = f"Expected return_when in {{{exp}}}, got {return_when}"
        raise ValueError(s)

    done = set()
    pend = set(aws)

    for aw in aws:
        loop.fifo_wait(aw)

    while True:
        aw = await SuspendResume()

        done.add(aw)
        pend.remove(aw)

        if return_when == FIRST_COMPLETED and len(done) == 1:
            for aw in pend:
                loop.fifo_drop(aw, loop.task())
            break

        if return_when == ALL_COMPLETED and not pend:
            break

    return done, pend


def finish():
    raise FinishError()
