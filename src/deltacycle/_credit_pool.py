"""Credit Pool synchronization primitive"""

from __future__ import annotations

import heapq
from functools import cached_property
from types import TracebackType
from typing import Self

from ._kernel_if import KernelIf
from ._task import Blocking, Sendable, Task, TaskQueue


class _WaitQ(TaskQueue):
    """Priority queue for ordering task execution."""

    def __init__(self):
        # priority, index, task, n
        self._items: list[tuple[int, int, Task, int]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[int, Task, int]):
        priority, task, n = item
        task.link(self)
        heapq.heappush(self._items, (priority, self._index, task, n))
        self._index += 1

    def pop(self) -> tuple[Task, int]:
        _, _, task, n = heapq.heappop(self._items)
        task.unlink(self)
        return task, n

    def _find(self, task: Task) -> int:
        for i, (_, _, t, _) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task):
        index = self._find(task)
        self._items.pop(index)
        task.unlink(self)

    def peek(self):
        return self._items[0][-1]


class CreditPool(KernelIf, Sendable):
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

    def wait_push(self, priority: int, task: Task, n: int):
        self._waiting.push((priority, task, n))

    def wait_drop(self, task: Task):
        self._waiting.drop(task)

    def req(self, n: int = 1, priority: int = 0) -> ReqCredit:
        if n < 1:
            raise ValueError(f"Expected n ≥ 1, got {n}")

        return ReqCredit(self, n, priority)

    def put(self, n: int = 1):
        if n < 1:
            raise ValueError(f"Expected n ≥ 1, got {n}")

        # NOTE: Do NOT support deposit bypass
        if self._has_capacity and self._cnt + n > self._capacity:
            raise OverflowError(f"{self._cnt} + {n} > {self._capacity}")

        # Deposit credit
        assert self._cnt >= 0
        self._cnt += n

        while self._waiting and (self._cnt >= self._waiting.peek()):
            # Transfer credit
            task, n = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))
            self._cnt -= n

    def try_get(self, n: int = 1) -> bool:
        if n < 1:
            raise ValueError(f"Expected n ≥ 1, got {n}")

        if 0 <= self._cnt < n:
            # Deny credit
            return False

        if self._cnt >= n:
            # Withdraw credit
            self._cnt -= n
            return True

        assert False  # pragma: no cover

    async def get(self, n: int = 1, priority: int = 0):
        if n < 1:
            raise ValueError(f"Expected n ≥ 1, got {n}")

        if 0 <= self._cnt < n:
            # Await credit
            task = self._kernel.task()
            self.wait_push(priority, task, n)
            credits = await task.switch_coro()
            assert credits is self
        elif self._cnt >= n:
            # Withdraw credit
            self._cnt -= n
        else:
            assert False  # pragma: no cover


class ReqCredit(Blocking):
    def __init__(self, credits: CreditPool, n: int, priority: int):
        self._credits = credits
        self._n = n
        self._priority = priority

    async def __aenter__(self) -> Self:
        await self._credits.get(self._n, self._priority)
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception],
        exc: Exception,
        traceback: TracebackType,
    ):
        self._credits.put(self._n)

    def try_block(self, task: Task) -> bool:
        if self._credits.try_get(self._n):
            return False

        self._credits.wait_push(self._priority, task, self._n)
        return True

    @property
    def s(self) -> Sendable:
        return self._credits
