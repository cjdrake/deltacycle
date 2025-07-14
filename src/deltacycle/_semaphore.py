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

    @override
    def wait(self) -> bool:
        assert self._cnt >= 0
        return self._cnt == 0

    # def wait_for(self, p: Predicate, task: Task) -> None:
    #    raise NotImplementedError()  # pragma: no cover

    def wait_push(self, task: Task):
        self._waiting.push(task)

    def wait_drop(self, task: Task):
        self._waiting.drop(task)

    def dec(self):
        self._cnt -= 1

    def put(self):
        assert self._cnt >= 0
        if self._waiting:
            task = self._waiting.pop()
            self._kernel.remove_task_sched(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
        else:
            self._cnt += 1

    def try_get(self) -> bool:
        if self.wait():
            return False
        self._cnt -= 1
        return True

    async def get(self):
        if self.wait():
            task = self._kernel.task()
            self.wait_push(task)
            s = await self._kernel.switch_coro()
            assert s is self
        else:
            self.dec()


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
            self._kernel.remove_task_sched(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
        else:
            if self._cnt == self._maxcnt:
                raise ValueError("Cannot put")
            self._cnt += 1


class Lock(BoundedSemaphore):
    """Mutex lock to synchronize tasks."""

    def __init__(self):
        super().__init__(value=1)
