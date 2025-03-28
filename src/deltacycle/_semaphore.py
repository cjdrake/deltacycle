"""Semaphore synchronization primitive"""

from typing import override

from ._loop_if import LoopIf
from ._suspend_resume import SuspendResume
from ._task import TaskState, WaitFifo


class Semaphore(LoopIf):
    """Semaphore to synchronize tasks.

    Permits number of release() > resource count.
    """

    def __init__(self, value: int = 1):
        if value < 1:
            raise ValueError(f"Expected value >= 1, got {value}")
        self._value = value
        self._cnt = value
        self._task_fifo = WaitFifo()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        self.release()

    async def acquire(self):
        assert self._cnt >= 0
        if self.locked():
            task = self._loop.task()
            self._task_fifo.push(task)
            task.set_state(TaskState.WAITING)
            await SuspendResume()
        else:
            self._cnt -= 1

    def try_acquire(self) -> bool:
        assert self._cnt >= 0
        if self.locked():
            return False
        self._cnt -= 1
        return True

    def release(self):
        assert self._cnt >= 0
        if self._task_fifo:
            task = self._task_fifo.pop()
            self._loop.call_soon(task, value=self)
        else:
            self._cnt += 1

    def locked(self) -> bool:
        return self._cnt == 0


class BoundedSemaphore(Semaphore):
    """Bounded Semaphore to synchronize tasks.

    Like Semaphore, but raises ValueError when
    number of release() > resource count.
    """

    @override
    def release(self):
        assert self._cnt >= 0
        if self._task_fifo:
            task = self._task_fifo.pop()
            self._loop.call_soon(task, value=self)
        else:
            if self._cnt == self._value:
                raise ValueError("Cannot release")
            self._cnt += 1


class Lock(BoundedSemaphore):
    """Mutex lock to synchronize tasks."""

    def __init__(self):
        super().__init__(value=1)
