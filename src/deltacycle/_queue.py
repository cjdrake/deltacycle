"""Queue synchronization primitive."""

from __future__ import annotations

import heapq
from collections import deque
from typing import Any

from ._kernel_if import KernelIf
from ._task import SupportsDropTask, Task


class _PortQ(SupportsDropTask):
    """Tasks wait for a slot to become available."""

    def __init__(self):
        # priority, index, task
        self._items: list[tuple[int, int, Task[Any]]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __len__(self) -> int:
        return len(self._items)

    def _find(self, task: Task[Any]) -> int:
        for i, (_, _, t) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task[Any]):
        index = self._find(task)
        del self._items[index]
        heapq.heapify(self._items)
        task._unlink(tq=self)

    def push(self, priority: int, task: Task[Any]):
        task._link(tq=self)
        heapq.heappush(self._items, (priority, self._index, task))
        self._index += 1

    def pop(self) -> Task[Any]:
        _, _, task = heapq.heappop(self._items)
        task._unlink(tq=self)
        return task


class _PortLock[T](SupportsDropTask):
    def __init__(self, parent: Queue[T]):
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


class _GetLock[T](_PortLock[T]):
    def drop(self, task: Task[Any]):
        assert self._task is task

        self.release()

        # Task was interrupted before get completed.
        # Queue should still have a free item.
        assert not self._parent.empty()

        if self._parent._getq:
            # Get task waiting, port unlocked, item available
            self.acquire(task=self._parent._getq_pop())


class _PutLock[T](_PortLock[T]):
    def drop(self, task: Task[Any]):
        assert self._task is task

        self.release()

        # Task was interrupted before put completed.
        # Queue should still have a free slot.
        assert not self._parent.full()

        if self._parent._putq:
            # Put task waiting, port unlocked, space available
            self.acquire(task=self._parent._putq_pop())


class Queue[T](KernelIf):
    """Producer / Consumer FIFO Queue.

    Has both blocking and non-blocking put and get interfaces.
    If capacity is a positive number, the queue has *capacity* slots.
    If capacity is zero or a negative number, the queue has infinite slots.

    The put interface will block only when it is full.
    The get interface will block only when it is empty.

    An infinite queue will never be full.
    Its size is subject only to the machine's memory limitations.
    """

    def __init__(self, capacity: int = 0):
        self._capacity = capacity
        self._has_capacity = capacity > 0

        self._items: deque[T] = deque()

        # Tasks waiting to get an item
        self._getq = _PortQ()

        # Tasks waiting to put an item
        self._putq = _PortQ()

        # Lock ensures gets are atomic
        self._get_lock = _GetLock(parent=self)

        # Lock ensures puts are atomic
        self._put_lock = _PutLock(parent=self)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def capacity(self) -> int | None:
        return self._capacity if self._has_capacity else None

    def empty(self) -> bool:
        return len(self._items) == 0

    def full(self) -> bool:
        return self._has_capacity and len(self._items) == self._capacity

    def _getq_ready(self) -> bool:
        return bool(self._getq) and not self.empty()

    def _getq_pop(self) -> Task[Any]:
        task = self._getq.pop()
        self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task

    def _putq_ready(self) -> bool:
        return bool(self._putq) and not self.full()

    def _putq_pop(self) -> Task[Any]:
        task = self._putq.pop()
        self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return task

    def _put(self, item: T):
        self._items.append(item)
        if self._getq and not self._get_lock:
            # Get task waiting, port unlocked, NEW item available
            self._get_lock.acquire(task=self._getq_pop())

    def try_put(self, item: T) -> bool:
        """Nonblocking put: Return True if a put attempt is successful."""
        if self.full() or self._put_lock:
            return False

        self._put(item)
        return True

    async def put(self, item: T, priority: int = 0):
        """Block until there is space for an item."""
        if self.full() or self._put_lock:
            task = self._kernel.check_task()

            self._putq.push(priority, task)
            y = await task.switch_coro()
            assert y is None

            # Wakeup: complete put
            self._put(item)
            self._put_lock.release()

            if self._putq_ready():
                # Put task waiting, port unlocked, space available
                self._put_lock.acquire(task=self._putq_pop())
        else:
            self._put(item)

    def _get(self) -> T:
        item = self._items.popleft()
        if self._putq and not self._put_lock:
            # Put task waiting, port unlocked, NEW space available
            self._put_lock.acquire(task=self._putq_pop())
        return item

    def try_get(self) -> tuple[bool, T | None]:
        """Nonblocking get.

        Returns:
            If the get is successful, ``(True, item)``;
            If unsuccessful, ``(False, None)``.
        """
        if self.empty() or self._get_lock:
            return False, None

        item = self._get()
        return True, item

    async def get(self, priority: int = 0) -> T:
        """Block until an item is available."""
        if self.empty() or self._get_lock:
            task = self._kernel.check_task()

            self._getq.push(priority, task)
            y = await task.switch_coro()
            assert y is None

            # Wakeup: complete get
            item = self._get()
            self._get_lock.release()

            if self._getq_ready():
                # Get task waiting, port unlocked, item available
                self._get_lock.acquire(task=self._getq_pop())

            return item
        else:
            return self._get()
