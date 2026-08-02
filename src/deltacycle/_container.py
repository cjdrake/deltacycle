"""Container synchronization primitive."""

from typing import Any

from ._kernel_if import KernelIf
from ._task import CreditQ, Task


class Container(KernelIf):
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
        self._has_capacity = capacity > 0

        # Credit count
        self._cnt: int = 0

        # Tasks waiting to get credit
        self._getq = CreditQ()

        # Tasks waiting to put credit
        self._putq = CreditQ()

    def __len__(self) -> int:
        return self._cnt

    @property
    def capacity(self) -> int | None:
        return self._capacity if self._has_capacity else None

    def _check_cnt(self):
        assert self._cnt >= 0
        assert not self._has_capacity or self._cnt <= self._capacity

    def _check_n(self, n: int):
        if n < 1:
            raise ValueError(f"Expected n ≥ 1, got {n}")
        if self._has_capacity and n > self._capacity:
            raise ValueError(f"Expected n ≤ {self._capacity}, got {n}")

    def _empty(self, n: int) -> bool:
        return self._cnt < n

    def _full(self, n: int) -> bool:
        return self._has_capacity and (self._cnt + n) > self._capacity

    def _getq_pop(self) -> tuple[Task[Any], int]:
        task, n = self._getq.pop()
        self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task, n

    def _putq_pop(self) -> tuple[Task[Any], int]:
        task, n = self._putq.pop()
        self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task, n

    def _put(self, n: int):
        self._cnt += n

    def try_put(self, n: int = 1) -> bool:
        self._check_cnt()
        self._check_n(n)

        if self._full(n):
            return False

        self._put(n)
        return True

    async def put(self, n: int = 1, priority: int = 0):
        self._check_cnt()
        self._check_n(n)

        if self._full(n):
            task = self._kernel.check_task()
            self._putq.push(priority, task, n)
            y = await task.switch_coro()
            assert y is None
        else:
            self._put(n)

        while self._getq and (self._cnt >= self._getq.peek()):
            # Transfer credit
            _, n = self._getq_pop()
            self._get(n)

    def _get(self, n: int):
        self._cnt -= n

    def try_get(self, n: int = 1) -> bool:
        self._check_cnt()
        self._check_n(n)

        if self._empty(n):
            return False

        self._get(n)
        return True

    async def get(self, n: int = 1, priority: int = 0):
        self._check_cnt()
        self._check_n(n)

        if self._empty(n):
            task = self._kernel.check_task()
            self._getq.push(priority, task, n)
            y = await task.switch_coro()
            assert y is None
        else:
            self._get(n)

        while self._putq and (self._cnt + self._putq.peek()) <= self._capacity:
            # Transfer credit
            _, n = self._putq_pop()
            self._put(n)
