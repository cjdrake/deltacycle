"""Semaphore synchronization primitive"""

from typing import override

from ._suspend_resume import SuspendResume


class Semaphore:
    """Semaphore to synchronize tasks."""

    def __init__(self, value: int = 1):
        if value < 1:
            raise ValueError(f"Expected value >= 1, got {value}")
        self._value = value
        self._cnt = value

    @property
    def _loop(self):
        from ._sim import get_running_loop  # pylint: disable=import-outside-toplevel

        return get_running_loop()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        self.release()

    async def acquire(self):
        assert self._cnt >= 0
        if self._cnt == 0:
            self._loop.fifo_wait(self)
            await SuspendResume()
        else:
            self._cnt -= 1

    def try_acquire(self) -> bool:
        assert self._cnt >= 0
        if self._cnt == 0:
            return False
        self._cnt -= 1
        return True

    def release(self):
        assert self._cnt >= 0
        increment = self._loop.sem_release(self)
        if increment:
            self._cnt += 1

    def locked(self) -> bool:
        return self._cnt == 0


class BoundedSemaphore(Semaphore):

    @override
    def release(self):
        assert self._cnt >= 0
        increment = self._loop.sem_release(self)
        if increment:
            if self._cnt == self._value:
                raise ValueError("Cannot release")
            self._cnt += 1


class Lock(BoundedSemaphore):
    """Mutex lock to synchronize tasks."""

    def __init__(self):
        super().__init__(value=1)
