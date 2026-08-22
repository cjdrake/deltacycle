"""Semaphore synchronization primitive"""

from __future__ import annotations

import heapq
from types import TracebackType
from typing import Any, Self

from ._kernel_if import KernelIf
from ._task import Blocking, SupportsDropTask, Task


class _PortQ(SupportsDropTask):
    """Tasks wait for a slot to become available."""

    def __init__(self):
        # priority, index, task
        self._items: list[tuple[int, int, Task[Any], ReqSemaphore | None]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __len__(self) -> int:
        return len(self._items)

    def _find(self, task: Task[Any]) -> int:
        for i, (_, _, t, _) in enumerate(self._items):
            if t is task:
                return i
        raise ValueError(f"Task not in queue: {task}")  # pragma: no cover

    def drop(self, task: Task[Any]):
        index = self._find(task)
        del self._items[index]
        heapq.heapify(self._items)
        task._unlink(tq=self)

    def push(self, priority: int, task: Task[Any], req: ReqSemaphore | None):
        task._link(tq=self)
        heapq.heappush(self._items, (priority, self._index, task, req))
        self._index += 1

    def pop(self) -> tuple[Task[Any], ReqSemaphore | None]:
        _, _, task, req = heapq.heappop(self._items)
        task._unlink(tq=self)
        return task, req


class _PortLock(SupportsDropTask):
    def __init__(self, parent: Semaphore):
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

        # Task was interrupted before get completed.
        # Semaphore should still have a free credit.
        assert not self._parent._empty()

        if self._parent._getq:
            # Get task waiting, port unlocked, credit available
            self.acquire(task=self._parent._getq_pop())


class Semaphore(KernelIf):
    def __init__(self, value: int = 0, capacity: int = 0):
        self._capacity = capacity
        self._has_capacity = capacity > 0

        if value < 0:
            raise ValueError(f"Expected value ≥ 0, got {value}")
        if self._has_capacity and value > capacity:
            raise ValueError(f"Expected value ≤ {capacity}, got {value}")

        # Credit count
        self._cnt = value

        # Tasks waiting to get a credit
        self._getq = _PortQ()

        # Lock ensures gets are atomic
        self._get_lock = _GetLock(parent=self)

    @property
    def capacity(self) -> int | None:
        return self._capacity if self._has_capacity else None

    def _empty(self) -> bool:
        return self._cnt == 0

    def _full(self) -> bool:
        return self._has_capacity and self._cnt == self._capacity

    def _check_cnt(self):
        assert self._cnt >= 0
        assert not self._has_capacity or self._cnt <= self._capacity

    def _getq_ready(self) -> bool:
        return bool(self._getq) and not self._empty()

    def _getq_pop(self) -> Task[Any]:
        task, req = self._getq.pop()
        if req is not None:
            self._kernel._forks.clr(task, req)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, req))
        else:
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task

    def req(self, priority: int = 0) -> ReqSemaphore:
        return ReqSemaphore(self, priority)

    def _put(self):
        self._cnt += 1
        if self._getq and not self._get_lock:
            # Get task waiting, port unlocked, NEW credit available
            self._get_lock.acquire(task=self._getq_pop())

    def put(self):
        self._check_cnt()

        if self._full():
            raise OverflowError(f"{self._cnt} + 1 > {self._capacity}")

        self._put()

    def _get(self):
        self._cnt -= 1

    def try_get(self) -> bool:
        self._check_cnt()

        if self._empty():
            return False

        if self._get_lock:
            task = self._kernel.check_task()
            if task is not self._get_lock._task:
                return False
            self._get_lock.release()

        self._get()
        return True

    async def get(self, priority: int = 0):
        self._check_cnt()

        # TODO(cjdrake): Review case: task == _get_lock._task
        if self._empty() or self._get_lock:
            task = self._kernel.check_task()

            self._getq.push(priority, task, req=None)
            y = await task.switch_coro()
            assert y is None

            # Wakeup: complete get
            self._get()
            self._get_lock.release()

            if self._getq_ready():
                # Get task waiting, port unlocked, credit available
                self._get_lock.acquire(task=self._getq_pop())
        else:
            self._get()


class ReqSemaphore(Blocking):
    def __init__(self, sem: Semaphore, priority: int = 0):
        self._semaphore = sem
        self._priority = priority

    @property
    def semaphore(self) -> Semaphore:
        return self._semaphore

    async def __aenter__(self) -> Self:
        await self._semaphore.get(self._priority)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ):
        self._semaphore.put()

    # Blocking
    def try_block(self, task: Task[Any]) -> Blocking.Type:
        if self._semaphore.try_get():
            return Blocking.Type.PERM_NONBLOCKING

        self._semaphore._getq.push(self._priority, task, req=self)
        return Blocking.Type.TEMP_BLOCKING

    def unblock(self, task: Task[Any]):
        self._semaphore._getq.drop(task)


class Lock(Semaphore):
    def __init__(self):
        super().__init__(value=1, capacity=1)
