"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Generator

from ._kernel_if import KernelIf
from ._task import Task, WaitFifo


class Event(KernelIf):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = WaitFifo()

    def __bool__(self) -> bool:
        return self._flag

    def __await__(self) -> Generator[None, Event, Event]:
        if not self._flag:
            task = self._kernel.task()
            self._wait(task)
            e = yield from self._kernel.switch_gen()
            assert e is self

        return self

    def __or__(self, other: Event) -> EventList:
        return EventList(self, other)

    def _wait(self, task: Task):
        self._waiting.push(task)
        self._kernel._task2events[task].add(self)

    def _set(self):
        while self._waiting:
            task = self._waiting.pop()

            # Remove task from Event waiting queues
            self._kernel._task2events[task].remove(self)
            while self._kernel._task2events[task]:
                e = self._kernel._task2events[task].pop()
                e._waiting.drop(task)
            del self._kernel._task2events[task]

            # Send event id to parent task
            self._kernel.call_soon(task, value=(Task.Command.RESUME, self))

    def set(self):
        self._flag = True
        self._set()

    def clear(self):
        self._flag = False


class EventList(KernelIf):
    def __init__(self, *events: Event):
        self._events = events

    def __await__(self) -> Generator[None, Event, Event]:
        task = self._kernel.task()

        fst = None
        for e in self._events:
            if e:
                fst = e
                break

        # No events set yet
        if fst is None:
            # Await first event to be set
            for e in self._events:
                e._wait(task)
            fst = yield from self._kernel.switch_gen()
            assert isinstance(fst, Event)

        return fst

    def __or__(self, other: Event) -> EventList:
        return EventList(*self._events, other)
