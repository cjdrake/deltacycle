"""Semaphore synchronization primitive"""

from types import TracebackType
from typing import override

from ._loop_if import LoopIf
from ._task import TaskCommand, WaitFifo


class Semaphore(LoopIf):
    """Semaphore to synchronize tasks.

    Permits number of put() > resource count.
    """

    def __init__(self, value: int = 1):
        if value < 1:
            raise ValueError(f"Expected value >= 1, got {value}")
        self._cnt = value
        self._waiting = WaitFifo()

    async def __aenter__(self):
        await self.get()
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception],
        exc: Exception,
        traceback: TracebackType,
    ):
        self.put()

    def put(self):
        assert self._cnt >= 0
        if self._waiting:
            task = self._waiting.pop()
            self._loop.call_soon(task, value=(TaskCommand.RESUME, None))
        else:
            self._cnt += 1

    def try_get(self) -> bool:
        assert self._cnt >= 0
        if self._cnt == 0:
            return False
        self._cnt -= 1
        return True

    async def get(self):
        assert self._cnt >= 0
        if self._cnt == 0:
            task = self._loop.task()
            self._waiting.push(task)
            await self._loop.switch_coro()
        else:
            self._cnt -= 1


class BoundedSemaphore(Semaphore):
    """Bounded Semaphore to synchronize tasks.

    Like Semaphore, but raises ValueError when
    number of put() > resource count.
    """

    def __init__(self, value: int = 1):
        super().__init__(value)
        self._maxcnt = value

    @override
    def put(self):
        assert self._cnt >= 0
        if self._waiting:
            task = self._waiting.pop()
            self._loop.call_soon(task, value=(TaskCommand.RESUME, None))
        else:
            if self._cnt == self._maxcnt:
                raise ValueError("Cannot put")
            self._cnt += 1


class Lock(BoundedSemaphore):
    """Mutex lock to synchronize tasks."""

    def __init__(self):
        super().__init__(value=1)
