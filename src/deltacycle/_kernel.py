"""Execution Kernel"""

import heapq
import logging
from collections.abc import Generator
from enum import IntEnum
from typing import Any

from ._task import Cancellable, Task, TaskArgs, TaskCoro, TaskQueue
from ._variable import Variable

logger = logging.getLogger("deltacycle")


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

    def __await__(self) -> Generator[None, Cancellable | None, Cancellable | None]:
        # Suspend
        value = yield
        # Resume
        return value


class _Finish(Exception):
    """Force the simulation to stop."""


class _PendQueue(TaskQueue):
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


class Kernel:
    """Simulation Kernel.

    Responsible for:

    * Scheduling and executing all tasks
    * Updating all model state

    This is a low level API.
    User code is not expected to interact with it directly.
    To run a simulation, use the run and step functions.
    """

    _index = 0

    class State(IntEnum):
        """
        Transitions::

            INIT -> RUNNING -> COMPLETED
                            -> FINISHED
        """

        # Initialized
        INIT = 0b001

        # Currently running
        RUNNING = 0b010

        # All tasks completed
        COMPLETED = 0b100

        # finish() called
        FINISHED = 0b101

    _done = State.COMPLETED & State.FINISHED

    _state_transitions = {
        State.INIT: {
            State.RUNNING,
        },
        State.RUNNING: {
            State.COMPLETED,
            State.FINISHED,
        },
    }

    init_time = -1
    start_time = 0

    main_name = "main"
    main_priority = 0

    def __init__(self):
        self._name = f"Kernel-{self.__class__._index}"
        self.__class__._index += 1

        self._state = self.State.INIT

        # Simulation time
        self._time: int = self.init_time

        # Main task
        self._main: Task | None = None

        # Currently executing task
        self._task: Task | None = None
        self._task_index = 0

        # Task queue
        self._queue = _PendQueue()

        # Serial Tasks
        self._schedule: dict[Task, set[Cancellable]] = {}

        # Model variables
        self._touched: set[Variable] = set()

    def _set_state(self, state: State):
        assert state in self._state_transitions[self._state]
        logger.debug("%s: %s => %s", self._name, self._state.name, state.name)
        self._state = state

    def state(self) -> State:
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

    def done(self) -> bool:
        return bool(self._state & self._done)

    # Scheduling methods
    def call_soon(self, task: Task, args: TaskArgs):
        self._queue.push((self._time, task, args))

    def call_later(self, delay: int, task: Task, args: TaskArgs):
        self._queue.push((self._time + delay, task, args))

    def call_at(self, when: int, task: Task, args: TaskArgs):
        self._queue.push((when, task, args))

    def create_main(self, coro: TaskCoro):
        assert self._time == self.init_time
        self._main = Task(coro, self.main_name, self.main_priority)
        self.call_at(self.start_time, self._main, args=(Task.Command.START,))

    def create_task(
        self,
        coro: TaskCoro,
        name: str | None = None,
        priority: int = 0,
    ) -> Task:
        assert self._time >= self.start_time
        if name is None:
            name = f"Task-{self._task_index}"
            self._task_index += 1
        task = Task(coro, name, priority)
        self.call_soon(task, args=(Task.Command.START,))
        return task

    async def switch_coro(self) -> Cancellable | None:
        assert self._task is not None
        # Suspend
        self._task._set_state(Task.State.PENDING)
        value = await _SuspendResume()
        # Resume
        return value

    def switch_gen(self) -> Generator[None, Cancellable, Cancellable]:
        assert self._task is not None
        # Suspend
        self._task._set_state(Task.State.PENDING)
        value = yield
        # Resume
        return value

    def fork(self, task: Task, *cs: Cancellable):
        self._schedule[task] = set(cs)

    def join_any(self, task: Task, c: Cancellable):
        if task in self._schedule:
            cs = self._schedule[task]
            cs.remove(c)
            while cs:
                c = cs.pop()
                c.cancel(task)
            del self._schedule[task]

    def touch(self, v: Variable):
        self._touched.add(v)

    def _update(self):
        while self._touched:
            v = self._touched.pop()
            v.update()

    def _start(self):
        if self._state is self.State.INIT:
            self._set_state(self.State.RUNNING)
        elif self._state is not self.State.RUNNING:
            s = f"Kernel has invalid state: {self._state.name}"
            raise RuntimeError(s)

    def _iter_time_slot(self, time: int) -> Generator[tuple[Task, TaskArgs], None, None]:
        """Iterate through all tasks in a time slot.

        The first task has already been peeked.
        This is a do-while loop.
        """
        task, value = self._queue.pop()
        yield (task, value)
        while self._queue and self._queue.peek() == time:
            task, value = self._queue.pop()
            yield (task, value)

    def _finish(self):
        self._queue.clear()
        # self._task_deps.clear()
        self._touched.clear()
        self._set_state(self.State.FINISHED)

    def _call(self, limit: int | None):
        self._start()

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
            for task, args in self._iter_time_slot(time):
                self._task = task
                try:
                    task._do_run(args)
                except _Finish:
                    self._finish()
                    return
                except StopIteration as exc:
                    task._do_result(exc)
                except Exception as exc:
                    task._do_except(exc)

            # Update simulation state
            self._update()

        # All tasks exhausted
        self._set_state(self.State.COMPLETED)

    def _iter(self) -> Generator[int, None, None]:
        self._start()

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
            for task, args in self._iter_time_slot(time):
                self._task = task
                try:
                    task._do_run(args)
                except _Finish:
                    self._finish()
                    return
                except StopIteration as exc:
                    task._do_result(exc)
                except Exception as exc:
                    task._do_except(exc)

            # Update simulation state
            self._update()

        # All tasks exhausted
        self._set_state(self.State.COMPLETED)

    def __call__(self, ticks: int | None = None, until: int | None = None):
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
            case int(), int():
                limit = max(self.start_time, self._time) + ticks
                limit = min(limit, until)
            case _:
                s = "Expected either ticks or until to be int | None"
                raise TypeError(s)

        self._call(limit)

    def __iter__(self) -> Generator[int, None, None]:
        yield from self._iter()


def finish():
    """Halt all incomplete coroutines, and immediately exit simulation.

    Clear all kernel data, and transition state to FINISHED.
    """
    raise _Finish()
