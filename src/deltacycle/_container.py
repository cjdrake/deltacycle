"""Queue synchronization primitive."""

import heapq
from functools import cached_property

from ._kernel_if import KernelIf
from ._task import Sendable, Task, TaskQueue


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


class Container(KernelIf, Sendable):
    """Producer / Consumer Resource Container.

    Has both blocking and non-blocking put and get interfaces.
    If capacity is a positive number, the container has *capacity* slots.
    If capacity is zero or a negative number, the container has infinite slots.

    The put interface will block only when it is full.
    The get interface will block only when it is empty.

    An infinite container will never be full.
    Its size is subject only to the machine's memory limitations.
    """

    def __init__(self, capacity: int = 0):
        self._capacity = capacity
        self._cnt: int = 0
        self._getq = _WaitQ()
        self._putq = _WaitQ()

    def __len__(self) -> int:
        return self._cnt

    @cached_property
    def _has_capacity(self) -> bool:
        return self._capacity > 0

    def _check_cnt(self):
        assert self._cnt >= 0
        assert not self._has_capacity or self._cnt <= self._capacity

    def _check_n(self, n: int):
        if n < 1:
            raise ValueError(f"Expected n ≥ 1, got {n}")
        if self._has_capacity and n > self._capacity:
            raise ValueError(f"Expected n ≤ {self._capacity}, got {n}")

    def try_put(self, n: int = 1) -> bool:
        self._check_cnt()
        self._check_n(n)

        if self._has_capacity and (self._cnt + n) > self._capacity:
            return False

        # Put credit
        self._cnt += n
        return True

    async def put(self, n: int = 1, priority: int = 0):
        self._check_cnt()
        self._check_n(n)

        if self._has_capacity and (self._cnt + n) > self._capacity:
            task = self._kernel.task()
            self._putq.push((priority, task, n))
            y = await task.switch_coro()
            assert y is None
        else:
            # Put credit
            self._cnt += n

        while self._getq and (self._cnt >= self._getq.peek()):
            # Transfer credit
            task, n = self._getq.pop()
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))
            self._cnt -= n

    def try_get(self, n: int = 1) -> bool:
        self._check_cnt()
        self._check_n(n)

        if self._cnt < n:
            return False

        # Get credit
        self._cnt -= n
        return True

    async def get(self, n: int = 1, priority: int = 0):
        self._check_cnt()
        self._check_n(n)

        if self._cnt < n:
            task = self._kernel.task()
            self._getq.push((priority, task, n))
            y = await task.switch_coro()
            assert y is None
        else:
            # Get credit
            self._cnt -= n

        while self._putq and (self._cnt + self._putq.peek()) <= self._capacity:
            # Transfer credit
            task, n = self._putq.pop()
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))
            self._cnt += n
