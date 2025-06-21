"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Awaitable, Generator
from typing import Any

from ._loop_if import LoopIf
from ._task import Task, WaitFifo


class Event(Awaitable[Any], LoopIf):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = WaitFifo()

    def __bool__(self) -> bool:
        return self._flag

    def __await__(self) -> Generator[None, Event, Event]:
        if not self._flag:
            task = self._loop.task()
            self._wait(task)
            e: Event = yield from self._loop.switch_gen()
            assert e is self

        return self

    def _wait(self, task: Task):
        self._waiting.push(task)
        self._loop._task2events[task].add(self)

    def _set(self):
        while self._waiting:
            task = self._waiting.pop()

            # Remove task from Event waiting queues
            self._loop._task2events[task].remove(self)
            while self._loop._task2events[task]:
                e = self._loop._task2events[task].pop()
                e._waiting.drop(task)
            del self._loop._task2events[task]

            # Send event id to parent task
            self._loop.call_soon(task, value=self)

    def set(self):
        self._flag = True
        self._set()

    def clear(self):
        self._flag = False
