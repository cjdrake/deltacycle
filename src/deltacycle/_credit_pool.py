"""Credit Pool synchronization primitive"""

from __future__ import annotations

import heapq
from types import TracebackType
from typing import Any, Self

from ._kernel_if import KernelIf
from ._task import Blocking, SupportsDropTask, Task


class _PortQ(SupportsDropTask):
    """Tasks wait for credit to become available."""

    def __init__(self):
        # priority, index, task, n
        self._items: list[tuple[int, int, Task[Any], ReqCredit | None, int]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __len__(self) -> int:
        return len(self._items)

    def _find(self, task: Task[Any]) -> int:
        for i, (_, _, t, _, _) in enumerate(self._items):
            if t is task:
                return i
        raise ValueError(f"Task not in queue: {task}")  # pragma: no cover

    def drop(self, task: Task[Any]):
        index = self._find(task)
        del self._items[index]
        heapq.heapify(self._items)
        task._unlink(tq=self)

    def push(self, priority: int, task: Task[Any], req: ReqCredit | None, n: int):
        task._link(tq=self)
        heapq.heappush(self._items, (priority, self._index, task, req, n))
        self._index += 1

    def pop(self) -> tuple[Task[Any], ReqCredit | None]:
        _, _, task, req, _ = heapq.heappop(self._items)
        task._unlink(tq=self)
        return task, req

    def peek(self) -> int:
        assert self._items
        return self._items[0][-1]


class _PortLock(SupportsDropTask):
    def __init__(self, parent: CreditPool):
        self._parent = parent
        self._task: Task[Any] | None = None

    def __bool__(self) -> bool:
        return self._task is not None

    def acquire(self, task: Task[Any]):
        assert self._task is None

        task._link(tq=self)
        self._task = task

    def release(self):
        assert self._task is not None

        task = self._task
        self._task = None
        task._unlink(tq=self)


class _GetLock(_PortLock):
    def drop(self, task: Task[Any]):
        assert self._task is task

        self.release()

        # Task was interrupted before get completed

        if self._parent._getq_ready():
            # Get task waiting, port unlocked, credit available
            self.acquire(task=self._parent._getq_pop())


class CreditPool(KernelIf):
    def __init__(self, value: int = 0, capacity: int = 0):
        self._capacity = capacity
        self._has_capacity = capacity > 0

        if value < 0:
            raise ValueError(f"Expected value ≥ 0, got {value}")
        if self._has_capacity and value > capacity:
            raise ValueError(f"Expected value ≤ {capacity}, got {value}")

        # Credit count
        self._cnt = value

        # Tasks waiting to get credit
        self._getq = _PortQ()

        # Lock ensures gets are atomic
        self._get_lock = _GetLock(parent=self)

    def __len__(self) -> int:
        return self._cnt

    @property
    def capacity(self) -> int | None:
        return self._capacity if self._has_capacity else None

    def _empty(self, n: int) -> bool:
        return (self._cnt - n) < 0

    def _full(self, n: int) -> bool:
        return self._has_capacity and (self._cnt + n) > self._capacity

    def _check_cnt(self):
        assert self._cnt >= 0
        assert not self._has_capacity or self._cnt <= self._capacity

    def _check_n(self, n: int):
        if n < 1:
            raise ValueError(f"Expected n ≥ 1, got {n}")
        if self._has_capacity and n > self._capacity:
            raise ValueError(f"Expected n ≤ {self._capacity}, got {n}")

    def _getq_ready(self) -> bool:
        return bool(self._getq) and not self._empty(self._getq.peek())

    def _getq_pop(self) -> Task[Any]:
        task, req = self._getq.pop()
        if req is not None:
            self._kernel._forks.clr(task, req)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, req))
        else:
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task

    def req(self, n: int = 1, priority: int = 0) -> ReqCredit:
        self._check_n(n)
        return ReqCredit(self, n, priority)

    def _put(self, n: int):
        self._cnt += n
        if self._getq_ready() and not self._get_lock:
            # Get task waiting, port unlocked, NEW credit available
            self._get_lock.acquire(task=self._getq_pop())

    def put(self, n: int = 1):
        self._check_cnt()
        self._check_n(n)

        if self._full(n):
            raise OverflowError(f"{self._cnt} + {n} > {self._capacity}")

        self._put(n)

    def _get(self, n: int):
        self._cnt -= n

    def try_get(self, n: int = 1) -> bool:
        self._check_cnt()
        self._check_n(n)

        if self._empty(n) or self._get_lock:
            return False

        self._get(n)
        return True

    async def get(self, n: int = 1, priority: int = 0):
        self._check_cnt()
        self._check_n(n)

        if self._empty(n) or self._get_lock:
            task = self._kernel.check_task()

            self._getq.push(priority, task, req=None, n=n)
            y = await task.switch_coro()
            assert y is None

            # Wakeup: complete get
            self._get(n)
            self._get_lock.release()

            if self._getq_ready():
                # Get task waiting, port unlocked, credit available
                self._get_lock.acquire(task=self._getq_pop())
        else:
            # Get credit
            self._get(n)


class ReqCredit(Blocking):
    def __init__(self, credits: CreditPool, n: int, priority: int = 0):
        self._credits = credits
        self._n = n
        self._priority = priority

    @property
    def credits(self) -> CreditPool:
        return self._credits

    # Blocking
    async def __aenter__(self) -> Self:
        await self._credits.get(self._n, self._priority)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ):
        self._credits.put(self._n)

    def try_block(self, task: Task[Any]) -> bool:
        if self._credits.try_get(self._n):
            return False

        self._credits._getq.push(self._priority, task, req=self, n=self._n)
        return True

    def drop(self, task: Task[Any]):
        self._credits._getq.drop(task)
