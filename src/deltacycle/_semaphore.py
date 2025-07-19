"""Semaphore synchronization primitive"""

from types import TracebackType
from typing import Self, override

from ._kernel_if import KernelIf
from ._task import Schedulable, Task, TaskFifo


class Semaphore(KernelIf, Schedulable):
    """Semaphore to synchronize tasks.

    Permits number of put() > resource count.
    """

    def __init__(self, value: int = 1):
        if value < 1:
            raise ValueError(f"Expected value >= 1, got {value}")
        self._cnt = value
        self._waiting = TaskFifo()

    async def __aenter__(self) -> Self:
        await self.get()
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception],
        exc: Exception,
        traceback: TracebackType,
    ):
        self.put()

    def schedule(self, task: Task) -> bool:
        if not self._locked():
            self._dec()
            return True
        self._waiting.push(task)
        return False

    def cancel(self, task: Task):
        self._waiting.drop(task)

    def _locked(self) -> bool:
        assert self._cnt >= 0
        return self._cnt == 0

    def _dec(self):
        self._cnt -= 1

    def _inc(self):
        self._cnt += 1

    def put(self):
        assert self._cnt >= 0
        if self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
        else:
            self._inc()

    def try_get(self) -> bool:
        if not self._locked():
            self._dec()
            return True
        return False

    async def get(self):
        if not self._locked():
            self._dec()
        else:
            task = self._kernel.task()
            self._waiting.push(task)
            s = await self._kernel.switch_coro()
            assert s is self


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
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
        else:
            if self._cnt == self._maxcnt:
                raise ValueError("Cannot put")
            self._inc()


class Lock(BoundedSemaphore):
    """Mutex lock to synchronize tasks."""

    def __init__(self):
        super().__init__(value=1)
