"""Semaphore synchronization primitive"""

from __future__ import annotations

import heapq
from types import TracebackType
from typing import Self, override

from ._kernel_if import KernelIf
from ._task import Cancellable, Schedulable, Task, TaskQueue


class _SemWaitQ(TaskQueue):
    """Priority queue for ordering task execution."""

    def __init__(self):
        # priority, index, task
        self._items: list[tuple[int, int, Task]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[int, Task]):
        priority, task = item
        task._link(self)
        heapq.heappush(self._items, (priority, self._index, task))
        self._index += 1

    def pop(self) -> Task:
        _, _, task = heapq.heappop(self._items)
        task._unlink(self)
        return task

    def _find(self, task: Task) -> int:
        for i, (_, _, t) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task):
        index = self._find(task)
        self._items.pop(index)
        task._unlink(self)


class Semaphore(KernelIf, Cancellable):
    """Semaphore to synchronize tasks.

    Permits number of put() > resource count.
    """

    def __init__(self, value: int = 1):
        if value < 1:
            raise ValueError(f"Expected value ≥ 1, got {value}")
        self._cnt = value
        self._waiting = _SemWaitQ()

    def wait_push(self, p: int, t: Task):
        self._waiting.push((p, t))

    # NOTE: NOT Schedulable

    def cancel(self, task: Task):
        self._waiting.drop(task)

    def locked(self) -> bool:
        return self._cnt == 0

    def _dec(self):
        self._cnt -= 1

    def _inc(self):
        self._cnt += 1

    def req(self, priority: int = 0) -> Request:
        return Request(self, priority)

    def put(self):
        assert self._cnt >= 0
        if self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
        else:
            self._inc()

    def try_get(self) -> bool:
        assert self._cnt >= 0
        if not self.locked():
            self._dec()
            return True
        return False

    async def get(self, priority: int = 0):
        assert self._cnt >= 0
        if not self.locked():
            self._dec()
        else:
            task = self._kernel.task()
            self.wait_push(priority, task)
            s = await self._kernel.switch_coro()
            assert s is self


class Request(Schedulable):
    def __init__(self, s: Semaphore, p: int):
        self._s = s
        self._p = p

    async def __aenter__(self) -> Self:
        await self._s.get(self._p)
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception],
        exc: Exception,
        traceback: TracebackType,
    ):
        self._s.put()

    def blocking(self) -> bool:
        return self._s.locked()

    def schedule(self, task: Task):
        self._s.wait_push(self._p, task)

    @property
    def c(self) -> Cancellable:
        return self._s


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
