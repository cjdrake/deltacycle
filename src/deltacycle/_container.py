"""Container synchronization primitive."""

from __future__ import annotations

import heapq
from typing import Any

from ._kernel_if import KernelIf
from ._task import SupportsDropTask, Task


class _PortQ(SupportsDropTask):
    """Tasks wait for credit to become available."""

    def __init__(self):
        # priority, index, task, n
        self._items: list[tuple[int, int, Task[Any], int]] = []

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

    def push(self, priority: int, task: Task[Any], n: int):
        task._link(tq=self)
        heapq.heappush(self._items, (priority, self._index, task, n))
        self._index += 1

    def pop(self) -> Task[Any]:
        _, _, task, _ = heapq.heappop(self._items)
        task._unlink(tq=self)
        return task

    def peek(self) -> int:
        assert self._items
        return self._items[0][-1]


class _PortLock(SupportsDropTask):
    def __init__(self, parent: Container):
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
            # Get task waiting, port unlocked, resource available
            self.acquire(task=self._parent._getq_pop())


class _PutLock(_PortLock):
    def drop(self, task: Task[Any]):
        assert self._task is task

        self.release()

        # Task was interrupted before put completed

        if self._parent._putq_ready():
            # Put task waiting, port unlocked, space available
            self.acquire(task=self._parent._putq_pop())


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

        # Resource count
        self._cnt: int = 0

        # Tasks waiting to get resource
        self._getq = _PortQ()

        # Tasks waiting to put resource
        self._putq = _PortQ()

        # Lock ensures gets are atomic
        self._get_lock = _GetLock(parent=self)

        # Lock ensures puts are atomic
        self._put_lock = _PutLock(parent=self)

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
        task = self._getq.pop()
        self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task

    def _putq_ready(self) -> bool:
        return bool(self._putq) and not self._full(self._putq.peek())

    def _putq_pop(self) -> Task[Any]:
        task = self._putq.pop()
        self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task

    def _put(self, n: int):
        self._cnt += n
        if self._getq_ready() and not self._get_lock:
            # Get task waiting, port unlocked, NEW resource available
            self._get_lock.acquire(task=self._getq_pop())

    def try_put(self, n: int = 1) -> bool:
        self._check_cnt()
        self._check_n(n)

        if self._full(n):
            return False

        if self._put_lock:
            task = self._kernel._check_task()
            if task is not self._put_lock._task:
                return False
            self._put_lock.release()

        self._put(n)
        return True

    async def put(self, n: int = 1, priority: int = 0):
        self._check_cnt()
        self._check_n(n)

        if self._full(n) or self._put_lock:
            task = self._kernel._check_task()

            self._putq.push(priority, task, n)
            y = await self._kernel._switch_coro()
            assert y is None

            # Wakeup: complete put
            self._put(n)
            self._put_lock.release()

            if self._putq_ready():
                # Put task waiting, port unlocked, space available
                self._put_lock.acquire(task=self._putq_pop())
        else:
            self._put(n)

    def _get(self, n: int):
        self._cnt -= n
        if self._putq_ready() and not self._put_lock:
            # Put task waiting, port unlocked, NEW space available
            self._put_lock.acquire(task=self._putq_pop())

    def try_get(self, n: int = 1) -> bool:
        self._check_cnt()
        self._check_n(n)

        if self._empty(n):
            return False

        if self._get_lock:
            task = self._kernel._check_task()
            if task is not self._get_lock._task:
                return False
            self._get_lock.release()

        self._get(n)
        return True

    async def get(self, n: int = 1, priority: int = 0):
        self._check_cnt()
        self._check_n(n)

        if self._empty(n) or self._get_lock:
            task = self._kernel._check_task()

            self._getq.push(priority, task, n)
            y = await self._kernel._switch_coro()
            assert y is None

            # Wakeup: complete get
            self._get(n)
            self._get_lock.release()

            if self._getq_ready():
                # Get task waiting, port unlocked, resource available
                self._get_lock.acquire(task=self._getq_pop())
        else:
            self._get(n)
