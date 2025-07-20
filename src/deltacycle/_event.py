"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Generator
from typing import Self

from ._kernel_if import KernelIf
from ._task import Cancellable, SchedFifo, Schedulable, Task


class Event(KernelIf, Schedulable, Cancellable):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = SchedFifo()

    def __await__(self) -> Generator[None, Cancellable, Self]:
        if not self._flag:
            task = self._kernel.task()
            self._waiting.push(task)
            e = yield from self._kernel.switch_gen()
            assert e is self

        return self

    def schedule(self, task: Task) -> bool:
        if self._flag:
            return True
        self._waiting.push(task)
        return False

    @property
    def c(self) -> Event:
        return self

    def cancel(self, task: Task):
        self._waiting.drop(task)

    def __bool__(self) -> bool:
        return self._flag

    def set(self):
        self._flag = True
        self._waiting.load()

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))

    def clear(self):
        self._flag = False
