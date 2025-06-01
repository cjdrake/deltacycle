"""Event Loop"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Coroutine, Generator
from enum import IntEnum, auto
from typing import Any

from ._task import CancelledError, PendQueue, Task
from ._variable import Variable

logger = logging.getLogger("deltacycle")

type Predicate = Callable[[], bool]


class _SuspendResume(Awaitable[Any]):
    """Suspend/Resume current task.

    Use case:
    1. Current task A suspends itself: RUNNING => WAITING
    2. Event loop chooses PENDING tasks ..., T
    3. ... Task T wakes up task A w/ value X: WAITING => PENDING
    4. Event loop chooses PENDING tasks ..., A: PENDING => RUNNING
    5. Task A resumes with value X

    The value X can be used to pass information to the task.
    """

    def __await__(self) -> Generator[None, Any, Any]:
        # Suspend
        value = yield
        # Resume
        return value


class _FinishError(Exception):
    """Force the simulation to stop."""


def create_task(
    coro: Coroutine[Any, Any, Any],
    name: str | None = None,
    priority: int = 0,
) -> Task:
    """Create a task, and schedule it to start soon."""
    loop = get_running_loop()
    return loop.create_task(coro, name, priority)


class LoopState(IntEnum):
    """Loop State

    Transitions::

        INIT -> RUNNING -> COMPLETED
                        -> FINISHED
    """

    # Initialized
    INIT = auto()

    # Currently running
    RUNNING = auto()

    # All tasks completed
    COMPLETED = auto()

    # finish() called
    FINISHED = auto()


_loop_state_transitions = {
    LoopState.INIT: {LoopState.RUNNING},
    LoopState.RUNNING: {LoopState.COMPLETED, LoopState.FINISHED},
}


class Loop:
    """Simulation event loop.

    Responsible for:

    * Scheduling and executing all tasks
    * Updating all model state

    This is a low level API.
    User code is not expected to interact with it directly.
    To run a simulation, use the run and irun functions.
    """

    _index = 0

    init_time = -1
    start_time = 0

    main_priority = 0

    def __init__(self):
        self._name = f"Loop-{self.__class__._index}"
        self.__class__._index += 1

        self._state = LoopState.INIT

        # Simulation time
        self._time: int = self.init_time

        # Main task
        self._main: Task | None = None

        # Currently executing task
        self._task: Task | None = None

        # Task queue
        self._queue = PendQueue()

        # Model variables
        self._touched: set[Variable] = set()

    def _set_state(self, state: LoopState):
        assert state in _loop_state_transitions[self._state]
        logger.debug("%s: %s => %s", self._name, self._state.name, state.name)
        self._state = state

    def state(self) -> LoopState:
        """Current simulation state."""
        return self._state

    def time(self) -> int:
        """Current simulation time."""
        return self._time

    @property
    def main(self) -> Task:
        """Parent task of all other tasks."""
        assert self._main is not None
        return self._main

    def task(self) -> Task:
        """Currently running task."""
        assert self._task is not None
        return self._task

    _done_states = frozenset([LoopState.COMPLETED, LoopState.FINISHED])

    def done(self) -> bool:
        return self._state in self._done_states

    def finished(self) -> bool:
        return self._state is LoopState.FINISHED

    # Scheduling methods
    def call_soon(self, task: Task, value: Any = None):
        self._queue.push((self._time, task, value))

    def call_later(self, delay: int, task: Task, value: Any = None):
        self._queue.push((self._time + delay, task, value))

    def call_at(self, when: int, task: Task, value: Any = None):
        self._queue.push((when, task, value))

    def create_main(self, coro: Coroutine[Any, Any, Any]) -> Task:
        assert self._time == self.init_time
        main = Task(coro, name="main", priority=self.main_priority)
        self._main = main
        self.call_at(self.start_time, main)
        return main

    def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
        priority: int = 0,
    ) -> Task:
        assert self._time >= self.start_time
        task = Task(coro, name=name, priority=priority)
        self.call_soon(task)
        return task

    async def switch_coro(self) -> Any:
        assert self._task is not None
        # Suspend
        value = await _SuspendResume()
        # Resume
        return value

    def switch_gen(self) -> Generator[None, Any, Any]:
        assert self._task is not None
        # Suspend
        value = yield
        # Resume
        return value

    def touch(self, v: Variable):
        self._touched.add(v)

    def _update(self):
        while self._touched:
            v = self._touched.pop()
            v.update()

    def _finish(self):
        self._queue.clear()
        self._touched.clear()
        self._set_state(LoopState.FINISHED)

    def _iter_time_slot(self, time: int) -> Generator[tuple[Task, Any], None, None]:
        """Iterate through all tasks in a time slot.

        The first task has already been peeked.
        This is a do-while loop.
        """
        task, value = self._queue.pop()
        yield (task, value)
        while self._queue and self._queue.peek() == time:
            task, value = self._queue.pop()
            yield (task, value)

    def _kernel(self, limit: int | None):
        if self._state is LoopState.INIT:
            self._set_state(LoopState.RUNNING)
        elif self._state is not LoopState.RUNNING:
            s = f"Loop has invalid state: {self._state.name}"
            raise RuntimeError(s)

        while self._queue:
            # Peek when next event is scheduled
            time = self._queue.peek()

            # Protect against time traveling tasks
            assert time > self._time

            # Halt if we hit the run limit
            if limit is not None and time >= limit:
                return

            # Otherwise, advance to new timeslot
            self._time = time

            # Execute time slot
            for task, value in self._iter_time_slot(time):
                self._task = task
                try:
                    task._do_run(value)
                except StopIteration as e:
                    task._do_result(e)
                    assert task._refcnts.total() == 0
                except CancelledError as e:
                    task._do_cancel(e)
                    assert task._refcnts.total() == 0
                except _FinishError:
                    self._finish()
                    return
                except Exception as e:
                    task._do_except(e)
                    assert task._refcnts.total() == 0

            # Update simulation state
            self._update()

        # All tasks exhausted
        self._set_state(LoopState.COMPLETED)

    def run(self, ticks: int | None = None, until: int | None = None):
        # Determine the run limit
        match ticks, until:
            # Run until no tasks left
            case None, None:
                limit = None
            # Run until an absolute time
            case None, int():
                limit = until
            # Run until a number of ticks in the future
            case int(), None:
                limit = max(self.start_time, self._time) + ticks
            case _:
                s = "Expected either ticks or until to be int | None"
                raise TypeError(s)

        self._kernel(limit)

    def __iter__(self) -> Generator[int, None, None]:
        if self._state is LoopState.INIT:
            self._set_state(LoopState.RUNNING)
        elif self._state is not LoopState.RUNNING:
            s = f"Loop has invalid state: {self._state.name}"
            raise RuntimeError(s)

        while self._queue:
            # Peek when next event is scheduled
            time = self._queue.peek()

            # Protect against time traveling tasks
            assert time > self._time

            # Yield before entering new timeslot
            yield time

            # Advance to new timeslot
            self._time = time

            # Execute time slot
            for task, value in self._iter_time_slot(time):
                self._task = task
                try:
                    task._do_run(value)
                except StopIteration as e:
                    task._do_result(e)
                    assert task._refcnts.total() == 0
                except CancelledError as e:
                    task._do_cancel(e)
                    assert task._refcnts.total() == 0
                except _FinishError:
                    self._finish()
                    return
                except Exception as e:
                    task._do_except(e)
                    assert task._refcnts.total() == 0

            # Update simulation state
            self._update()

        # All tasks exhausted
        self._set_state(LoopState.COMPLETED)


_loop: Loop | None = None


def get_running_loop() -> Loop:
    """Return currently running loop.

    Returns:
        Loop instance

    Raises:
        RuntimeError: No loop, or loop is not currently running.
    """
    if _loop is None:
        raise RuntimeError("No loop")
    if _loop.state() is not LoopState.RUNNING:
        raise RuntimeError("Loop not RUNNING")
    return _loop


def get_loop() -> Loop | None:
    """Get the current event loop."""
    return _loop


def set_loop(loop: Loop | None = None):
    """Set the current event loop."""
    global _loop  # noqa: PLW0603
    _loop = loop


def get_current_task() -> Task:
    """Return currently running task.

    Returns:
        Task instance

    Raises:
        RuntimeError: No loop, or loop is not currently running.
    """
    loop = get_running_loop()
    return loop.task()


def now() -> int:
    """Return current simulation time.

    Returns:
        int time

    Raises:
        RuntimeError: No loop, or loop is not currently running.
    """
    loop = get_running_loop()
    return loop.time()


def _run_pre(coro: Coroutine[Any, Any, Any] | None, loop: Loop | None) -> Loop:
    if loop is None:
        set_loop(loop := Loop())
        if coro is None:
            raise ValueError("New loop requires a valid coro arg")
        assert coro is not None
        _ = loop.create_main(coro)
    else:
        set_loop(loop)
    return loop


def run(
    coro: Coroutine[Any, Any, Any] | None = None,
    loop: Loop | None = None,
    ticks: int | None = None,
    until: int | None = None,
) -> Any:
    """Run a simulation.

    If a simulation hits the run limit, it will exit and return None.
    That simulation may be resumed any number of times.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Optional main coroutine.
            Required if creating a new loop.
            Ignored if using an existing loop.
        loop: Optional Loop instance.
            If not provided, a new loop will be created.
        ticks: Optional relative run limit.
            If provided, run for *ticks* simulation time steps.
        until: Optional absolute run limit.
            If provided, run until *ticks* simulation time steps.

    Returns:
        If the main coroutine runs til completion, return its result.
        Otherwise, return ``None``.

    Raises:
        ValueError: Creating a new loop, but no coro provided.
        TypeError: ticks and until args conflict.
        RuntimeError: The loop is in an invalid state.
    """
    loop = _run_pre(coro, loop)
    loop.run(ticks, until)

    if loop.main.done():
        return loop.main.result()


def irun(
    coro: Coroutine[Any, Any, Any] | None = None,
    loop: Loop | None = None,
) -> Generator[int, None, Any]:
    """Iterate a simulation.

    Iterated simulations do not have a run limit.
    It is the user's responsibility to break at the desired time.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Optional main coroutine.
            Required if creating a new loop.
            Ignored if using an existing loop.
        loop: Optional Loop instance.
            If not provided, a new loop will be created.

    Yields:
        int time immediately *before* the next time slot executes.

    Returns:
        main coroutine result.

    Raises:
        ValueError: Creating a new loop, but no coro provided.
        TypeError: ticks and until args conflict.
        RuntimeError: The loop is in an invalid state.
    """
    loop = _run_pre(coro, loop)
    yield from loop

    assert loop.main.done()
    return loop.main.result()


async def sleep(delay: int):
    """Suspend the task, and wake up after a delay."""
    loop = get_running_loop()
    task = loop.task()
    loop.call_later(delay, task)
    await _SuspendResume()


async def changed(*vs: Variable) -> Variable:
    """Resume execution upon variable change.

    Suspend execution of the current task;
    Resume when any variable in the sensitivity list changes.

    Args:
        vs: Tuple of Variables, a sensitivity list.

    Returns:
        The Variable instance that triggered the task to resume.
    """
    loop = get_running_loop()
    task = loop.task()
    for v in vs:
        v._wait(v.changed, task)
    v: Variable = await loop.switch_coro()
    return v


async def touched(vps: dict[Variable, Predicate | None]) -> Variable:
    """Resume execution upon predicated variable change.

    Suspend execution of the current task;
    Resume when any variable in the sensitivity list changes,
    *and* the predicate function evaluates to True.
    If the predicate function is None, it will default to *any* change.

    Args:
        vps: Dict of Variable => Predicate mappings, a sensitivity list.

    Returns:
        The Variable instance that triggered the task to resume.
    """
    loop = get_running_loop()
    task = loop.task()
    for v, p in vps.items():
        if p is None:
            v._wait(v.changed, task)
        else:
            v._wait(p, task)
    v: Variable = await loop.switch_coro()
    return v


def finish():
    """Halt all incomplete coroutines, and immediately exit simulation.

    Clear all loop data, and transition state to FINISHED.
    """
    raise _FinishError()
