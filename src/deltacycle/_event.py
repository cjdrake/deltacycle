"""Event synchronization primitive"""

from collections.abc import Generator
from typing import Self

from ._kernel_if import KernelIf
from ._task import Predicate, SchedFifo, Schedulable, Task


class Event(KernelIf, Schedulable):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = SchedFifo()

    def __await__(self) -> Generator[None, Schedulable, Self]:
        if not self.is_set():
            task = self._kernel.task()
            self.wait_push(task)
            e = yield from self._kernel.switch_gen()
            assert e is self

        return self

    def wait_for(self, p: Predicate, task: Task):
        self._waiting.push((p, task))

    def _p(self) -> bool:
        return True

    def wait_push(self, task: Task):
        self._waiting.push((self._p, task))

    def wait_drop(self, task: Task):
        self._waiting.drop(task)

    def is_set(self) -> bool:
        return self._flag

    def __bool__(self) -> bool:
        return self._flag

    def set(self):
        self._flag = True
        self._waiting.load()

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.remove_task_sched(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))

    def clear(self):
        self._flag = False
