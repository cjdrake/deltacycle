"""Queue synchronization primitive."""

from collections import deque
from functools import cached_property

from ._kernel_if import KernelIf
from ._task import Task, WaitFifo


class Queue[T](KernelIf):
    """First-in, First-out (FIFO) queue."""

    def __init__(self, maxlen: int = 0):
        self._maxlen = maxlen
        self._items: deque[T] = deque()
        self._wait_not_empty = WaitFifo()
        self._wait_not_full = WaitFifo()

    def __len__(self) -> int:
        return len(self._items)

    @cached_property
    def _has_maxlen(self) -> bool:
        return self._maxlen > 0

    def empty(self) -> bool:
        """Return True if the queue is empty."""
        return not self._items

    def full(self) -> bool:
        """Return True if the queue is full."""
        return self._has_maxlen and len(self._items) == self._maxlen

    def _put(self, item: T):
        self._items.append(item)
        if self._wait_not_empty:
            task = self._wait_not_empty.pop()
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))

    def try_put(self, item: T) -> bool:
        """Nonblocking put: Return True if a put attempt is successful."""
        if self.full():
            return False

        self._put(item)
        return True

    async def put(self, item: T):
        """Block until there is space to put the item."""
        if self.full():
            task = self._kernel.task()
            self._wait_not_full.push(task)
            y = await self._kernel.switch_coro()
            assert y is None

        self._put(item)

    def _get(self) -> T:
        item = self._items.popleft()
        if self._wait_not_full:
            task = self._wait_not_full.pop()
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        return item

    def try_get(self) -> tuple[bool, T | None]:
        """Nonblocking get: Return True if a get attempt is successful."""
        if self.empty():
            return False, None

        item = self._get()
        return True, item

    async def get(self) -> T:
        """Block until an item is available to get."""
        if self.empty():
            task = self._kernel.task()
            self._wait_not_empty.push(task)
            y = await self._kernel.switch_coro()
            assert y is None

        return self._get()
