"""Semaphore synchronization primitive"""

from __future__ import annotations

import heapq
from types import TracebackType
from typing import Any, Self, override

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


class _Reservations(SupportsDropTask):
    def __init__(self, parent: Semaphore):
        self._parent = parent
        self._tasks: set[Task[Any]] = set()

    def __len__(self) -> int:
        return len(self._tasks)

    def drop(self, task: Task[Any]):
        # Suspend => Schedule => Interrupt[Put]
        self.pop(task)
        self._parent.put()

    def push(self, task: Task[Any]):
        assert task not in self._tasks
        task._link(tq=self)
        self._tasks.add(task)

    def pop(self, task: Task[Any]):
        self._tasks.remove(task)
        task._unlink(tq=self)


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
        self._rsvns = _Reservations(parent=self)

    @property
    def capacity(self) -> int | None:
        return self._capacity if self._has_capacity else None

    def _full(self) -> bool:
        return self._has_capacity and (self._cnt + len(self._rsvns) + 1) > self._capacity

    def _check_cnt(self):
        assert self._cnt >= 0
        assert not self._has_capacity or self._cnt <= self._capacity

    def req(self, priority: int = 0) -> ReqSemaphore:
        return ReqSemaphore(self, priority)

    def _transfer(self):
        task, req = self._getq.pop()

        # Suspend => Schedule => Resume[Get] | Interrupt[Put]
        self._rsvns.push(task)
        if req is not None:
            self._kernel._forks.clr(task, req)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, req))
        else:
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))

    def put(self):
        self._check_cnt()

        if self._full():
            raise OverflowError(f"{self._cnt} + 1 > {self._capacity}")

        if self._getq:
            # At least one waiting task: Transfer
            self._transfer()
        else:
            # No waiting tasks: Increment
            self._cnt += 1

    def _get(self):
        self._cnt -= 1

    def try_get(self) -> bool:
        self._check_cnt()

        if self._cnt >= 1:
            # At least one available credit: Decrement
            self._get()
            return True

        return False

    async def get(self, priority: int = 0):
        self._check_cnt()

        if self._cnt >= 1:
            # At least one available credit: Decrement
            self._get()
        else:
            # No available credit: Suspend
            task = self._kernel._check_task()
            self._getq.push(priority, task, req=None)
            y = await task._switch_coro()

            # Suspend => Schedule => Resume[Get]
            assert y is None
            self._rsvns.pop(task)


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
    def _is_blocking(self) -> bool:
        return self._semaphore._cnt == 0

    def _unblock(self, task: Task[Any]):
        self._semaphore._getq.drop(task)

    def _do_block(self, task: Task[Any]):
        self._semaphore._getq.push(self._priority, task, req=self)

    def _do_nonblock(self):
        self._semaphore._get()

    @override
    def _do_all_resume(self, task: Task[Any]):
        self._semaphore._rsvns.pop(task)
        self._semaphore.put()

    @override
    def _do_any_resume(self, task: Task[Any]):
        self._semaphore._rsvns.pop(task)


class Lock(Semaphore):
    def __init__(self):
        super().__init__(value=1, capacity=1)
