"""Semaphore synchronization primitive"""

from __future__ import annotations

import heapq
from functools import cached_property
from types import TracebackType
from typing import Self

from ._kernel_if import KernelIf
from ._task import Cancellable, Schedulable, Task, TaskQueue


class _WaitQ(TaskQueue):
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

    def __init__(self, value: int = 0, capacity: int = 0):
        self._capacity = capacity
        if value < 0:
            raise ValueError(f"Expected value ≥ 0, got {value}")
        if self._has_capacity and value > capacity:
            raise ValueError(f"Expected value ≤ {capacity}, got {value}")
        self._cnt = value
        self._waiting = _WaitQ()

    def __len__(self) -> int:
        return self._cnt

    @cached_property
    def _has_capacity(self) -> bool:
        return self._capacity > 0

    def wait_push(self, task: Task, priority: int):
        self._waiting.push((priority, task))

    # NOTE: NOT Schedulable

    def cancel(self, task: Task):
        self._waiting.drop(task)

    def req(self, priority: int = 0) -> ReqSemaphore:
        return ReqSemaphore(self, priority)

    def put(self):
        assert self._cnt >= 0

        if self._has_capacity and self._cnt == self._capacity:
            raise OverflowError(f"{self._cnt} + 1 > {self._capacity}")

        if self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
        else:
            self._cnt += 1

    def try_get(self) -> bool:
        assert self._cnt >= 0

        if self._cnt > 0:
            self._cnt -= 1
            return True
        return False

    async def get(self, priority: int = 0):
        assert self._cnt >= 0

        if self._cnt > 0:
            self._cnt -= 1
        else:
            task = self._kernel.task()
            self.wait_push(task, priority)
            s = await self._kernel.switch_coro()
            assert s is self


class ReqSemaphore(Schedulable):
    def __init__(self, sem: Semaphore, priority: int):
        self._sem = sem
        self._priority = priority

    async def __aenter__(self) -> Self:
        await self._sem.get(self._priority)
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception],
        exc: Exception,
        traceback: TracebackType,
    ):
        self._sem.put()

    def blocking(self) -> bool:
        return len(self._sem) == 0

    def schedule(self, task: Task):
        self._sem.wait_push(task, self._priority)

    @property
    def c(self) -> Cancellable:
        return self._sem


class Lock(Semaphore):
    """Mutex lock to synchronize tasks."""

    def __init__(self):
        super().__init__(value=1, capacity=1)
