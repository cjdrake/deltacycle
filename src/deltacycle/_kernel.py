"""Execution Kernel"""

import heapq
from collections.abc import Generator
from enum import IntEnum
from typing import Any
from weakref import WeakKeyDictionary

from ._task import Sendable, Task, TaskArgs, TaskCoro, TaskQueue
from ._variable import Variable


class _Finish(Exception):
    """Force the simulation to stop."""


class _PendQ(TaskQueue):
    """Priority queue for ordering task execution."""

    def __init__(self):
        # time, priority, index, task, value
        self._items: list[tuple[int, int, int, Task, Any]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[int, int, Task, Any]):
        time, priority, task, value = item
        task.link(self)
        heapq.heappush(self._items, (time, priority, self._index, task, value))
        self._index += 1

    def pop(self) -> tuple[Task, Any]:
        _, _, _, task, value = heapq.heappop(self._items)
        task.unlink(self)
        return (task, value)

    def _find(self, task: Task) -> int:
        for i, (_, _, _, t, _) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task):
        index = self._find(task)
        self._items.pop(index)
        task.unlink(self)

    def peek(self) -> int:
        return self._items[0][0]

    def clear(self):
        while self._items:
            self.pop()
        self._index = 0


class Kernel:
    """Simulation Kernel.

    Responsible for:

    * Scheduling and executing tasks
    * Updating model state

    This is a low level API.
    User code is not expected to interact with it directly.
    To run a simulation, use the ``run`` and ``step`` functions.
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

    task_priority = 0

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
        self._queue = _PendQ()

        # Task priorities
        self._task2priority = WeakKeyDictionary[Task, int]()

        # Forked Tasks
        self._forks: dict[Task, set[Sendable]] = {}

        # Model variables
        self._dirty_vars: set[Variable] = set()

    def _set_state(self, state: State):
        assert state in self._state_transitions[self._state]
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
        """Return True if the kernel is done.

        A kernel that is "done" either:

        * Exhaused all tasks (COMPLETED), or
        * Called ``finish`` (FINISHED)
        """
        return bool(self._state & self._done)

    # Scheduling methods
    def call_soon(self, task: Task, args: TaskArgs):
        priority = self._task2priority[task]
        self._queue.push((self._time, priority, task, args))

    def call_later(self, delay: int, task: Task, args: TaskArgs):
        priority = self._task2priority[task]
        self._queue.push((self._time + delay, priority, task, args))

    def call_at(self, when: int, task: Task, args: TaskArgs):
        priority = self._task2priority[task]
        self._queue.push((when, priority, task, args))

    def create_main(self, coro: TaskCoro) -> Task:
        assert self._time == self.init_time
        self._main = Task(coro, self.main_name)
        self._task2priority[self._main] = self.main_priority
        self.call_at(self.start_time, self._main, args=(Task.Command.START,))
        return self._main

    def create_task(
        self,
        coro: TaskCoro,
        name: str | None = None,
        **kwargs: Any,
    ) -> Task:
        assert self._time >= self.start_time
        if name is None:
            name = f"Task-{self._task_index}"
            self._task_index += 1
        task = Task(coro, name)
        self._task2priority[task] = kwargs.get("priority", self.task_priority)
        self.call_soon(task, args=(Task.Command.START,))
        return task

    def fork(self, task: Task, *ss: Sendable):
        self._forks[task] = set(ss)

    def join_any(self, task: Task, s: Sendable):
        if task in self._forks:
            ss = self._forks[task]
            ss.remove(s)
            while ss:
                s = ss.pop()
                s.wait_drop(task)
            del self._forks[task]

    def touch_var(self, v: Variable):
        self._dirty_vars.add(v)

    def _update_vars(self):
        while self._dirty_vars:
            v = self._dirty_vars.pop()
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
        self._forks.clear()
        self._dirty_vars.clear()
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
                    task.do_run(args)
                except _Finish:
                    self._finish()
                    return
                except StopIteration as exc:
                    task.do_result(exc)
                except Exception as exc:
                    task.do_except(exc)

            # Update simulation state
            self._update_vars()

        # Drop reference to last task
        self._task = None

        # All tasks exhausted
        self._set_state(self.State.COMPLETED)

    def __call__(self, ticks: int | None = None, until: int | None = None):
        # Determine the run limit
        if ticks is None:
            # Run until absolute limit, or no tasks left
            limit = until if until is not None else None
        else:
            # Run until relative limit
            limit = max(self.start_time, self._time) + ticks
            if until is not None:
                # Both relative & absolute given; clamp to soonest
                limit = min(limit, until)

        self._call(limit)

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
                    task.do_run(args)
                except _Finish:
                    self._finish()
                    return
                except StopIteration as exc:
                    task.do_result(exc)
                except Exception as exc:
                    task.do_except(exc)

            # Update simulation state
            self._update_vars()

        # Drop reference to last task
        self._task = None

        # All tasks exhausted
        self._set_state(self.State.COMPLETED)

    def __iter__(self) -> Generator[int, None, None]:
        yield from self._iter()


def finish():
    """Halt all incomplete coroutines, and immediately exit simulation.

    Clear all kernel data, and transition state to FINISHED.
    """
    raise _Finish()
