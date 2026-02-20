"""Semaphore synchronization primitive"""

from __future__ import annotations

from functools import cached_property
from types import TracebackType
from typing import Self

from ._kernel_if import KernelIf
from ._task import Blocking, SemaphoreQ, Sendable, Task


class Semaphore(KernelIf, Sendable):
    def __init__(self, value: int = 0, capacity: int = 0):
        self._capacity = capacity
        if value < 0:
            raise ValueError(f"Expected value ≥ 0, got {value}")
        if self._has_capacity and value > capacity:
            raise ValueError(f"Expected value ≤ {capacity}, got {value}")
        self._cnt = value
        self._waiting = SemaphoreQ()

    def __len__(self) -> int:
        return self._cnt

    @property
    def capacity(self) -> int | None:
        return self._capacity if self._has_capacity else None

    @cached_property
    def _has_capacity(self) -> bool:
        return self._capacity > 0

    def wait_push(self, priority: int, task: Task):
        self._waiting.push((priority, task))

    def wait_drop(self, task: Task):
        self._waiting.drop(task)

    def _check_cnt(self):
        assert self._cnt >= 0
        assert not self._has_capacity or self._cnt <= self._capacity

    def req(self, priority: int = 0) -> ReqSemaphore:
        return ReqSemaphore(self, priority)

    def put(self):
        self._check_cnt()

        if self._has_capacity and self._cnt == self._capacity:
            raise OverflowError(f"{self._cnt} + 1 > {self._capacity}")

        # Put credit
        self._cnt += 1

        if self._waiting:
            assert self._cnt == 1
            # Transfer credit
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
            self._cnt -= 1

    def try_get(self) -> bool:
        self._check_cnt()

        if self._cnt == 0:
            return False

        # Get credit
        self._cnt -= 1
        return True

    async def get(self, priority: int = 0):
        self._check_cnt()

        if self._cnt == 0:
            task = self._kernel.task()
            self.wait_push(priority, task)
            x = await task.switch_coro()
            assert x is self
        else:
            # Get credit
            self._cnt -= 1


class ReqSemaphore(Blocking):
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

    def try_block(self, task: Task) -> bool:
        if self._sem.try_get():
            return False

        self._sem.wait_push(self._priority, task)
        return True

    @property
    def x(self) -> Sendable:
        return self._sem


class Lock(Semaphore):
    def __init__(self):
        super().__init__(value=1, capacity=1)
