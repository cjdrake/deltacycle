"""Queue synchronization primitive."""

import heapq
from collections import deque
from functools import cached_property

from ._kernel_if import KernelIf
from ._task import Task, TaskQueue


class _WaitQ(TaskQueue):
    """Priority queue for ordering task execution."""

    def __init__(self):
        # priority, index, task
        self._items = list[tuple[int, int, Task]]()

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: tuple[int, Task]):
        priority, task = item
        task.link(self)
        heapq.heappush(self._items, (priority, self._index, task))
        self._index += 1

    def pop(self) -> Task:
        _, _, task = heapq.heappop(self._items)
        task.unlink(self)
        return task

    def _find(self, task: Task) -> int:
        for i, (_, _, t) in enumerate(self._items):
            if t is task:
                return i
        assert False  # pragma: no cover

    def drop(self, task: Task):
        index = self._find(task)
        self._items.pop(index)
        task.unlink(self)


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
        self._items = deque[T]()
        self._getq = _WaitQ()
        self._putq = _WaitQ()

    def __len__(self) -> int:
        return len(self._items)

    @property
    def capacity(self) -> int | None:
        return self._capacity if self._has_capacity else None

    @cached_property
    def _has_capacity(self) -> bool:
        return self._capacity > 0

    def empty(self) -> bool:
        return not self._items

    def full(self) -> bool:
        return self._has_capacity and len(self._items) == self._capacity

    def _put(self, item: T):
        self._items.append(item)
        if self._getq:
            task = self._getq.pop()
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))

    def try_put(self, item: T) -> bool:
        """Nonblocking put: Return True if a put attempt is successful."""
        if self.full():
            return False

        self._put(item)
        return True

    async def put(self, item: T, priority: int = 0):
        """Block until there is space for an item."""
        if self.full():
            task = self._kernel.task()
            self._putq.push((priority, task))
            y = await task.switch_coro()
            assert y is None

        self._put(item)

    def _get(self) -> T:
        item = self._items.popleft()
        if self._putq:
            task = self._putq.pop()
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return item

    def try_get(self) -> tuple[bool, T | None]:
        """Nonblocking get.

        Returns:
            If the get is successful, ``(True, item)``;
            If unsuccessful, ``(False, None)``.
        """
        if self.empty():
            return False, None

        item = self._get()
        return True, item

    async def get(self, priority: int = 0) -> T:
        """Block until an item is available."""
        if self.empty():
            task = self._kernel.task()
            self._getq.push((priority, task))
            y = await task.switch_coro()
            assert y is None

        return self._get()
