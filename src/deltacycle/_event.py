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
            self.wait()
            e = yield from self._kernel.switch_gen()
            assert e is self

        return self

    def __or__(self, other: Event) -> EventList:
        return EventList(self, other)

    def wait(self):
        task = self._kernel.task()
        self._waiting.push(task)
        self._kernel._task_deps[task].add(self)

    def _set(self):
        while self._waiting:
            task = self._waiting.pop()

            # Remove task from Event waiting queues
            self._kernel._task_deps[task].remove(self)
            while self._kernel._task_deps[task]:
                e = self._kernel._task_deps[task].pop()
                e._waiting.drop(task)
            del self._kernel._task_deps[task]

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
        fst = None
        for e in self._events:
            if e:
                fst = e
                break

        # No events set yet
        if fst is None:
            # Await first event to be set
            for e in self._events:
                e.wait()
            fst = yield from self._kernel.switch_gen()
            assert isinstance(fst, Event)

        return fst

    def __or__(self, other: Event) -> EventList:
        return EventList(*self._events, other)
