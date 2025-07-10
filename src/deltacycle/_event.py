"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Generator

from ._task import AwaitableIf, Task, WaitFifo


class Event(AwaitableIf):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = WaitFifo()

    def __await__(self) -> Generator[None, AwaitableIf, Event]:
        if not self.is_set():
            task = self._kernel.task()
            self.wait_push(task)
            e = yield from self._kernel.switch_gen()
            assert e is self

        return self

    def wait_push(self, task: Task):
        self._waiting.push(task)

    def wait_drop(self, task: Task):
        self._waiting.drop(task)

    def set(self):
        self._flag = True

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.remove_task_dep(task, self)
            self._kernel.call_soon(task, value=(Task.Command.RESUME, self))

    def is_set(self) -> bool:
        return self._flag

    def __bool__(self) -> bool:
        return self._flag

    def clear(self):
        self._flag = False
