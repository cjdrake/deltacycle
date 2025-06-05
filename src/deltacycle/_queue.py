"""Queue synchronization primitive."""

from collections import deque
from collections.abc import Sized

from ._loop_if import LoopIf
from ._task import WaitFifo


class Queue[T](Sized, LoopIf):
    """First-in, First-out (FIFO) queue."""

    def __init__(self, maxlen: int = 0):
        self._maxlen = maxlen
        self._items: deque[T] = deque()
        self._wait_not_empty = WaitFifo()
        self._wait_not_full = WaitFifo()

    def __len__(self) -> int:
        return len(self._items)

    def empty(self) -> bool:
        """Return True if the queue is empty."""
        return not self._items

    def full(self) -> bool:
        """Return True if the queue is full."""
        return self._maxlen > 0 and len(self._items) == self._maxlen

    def _put(self, item: T):
        self._items.append(item)
        if self._wait_not_empty:
            task = self._wait_not_empty.pop()
            self._loop.call_soon(task, value=None)

    def try_put(self, item: T) -> bool:
        """Nonblocking put: Return True if a put attempt is successful."""
        if self.full():
            return False
        self._put(item)
        return True

    async def put(self, item: T):
        """Block until there is space to put the item."""
        if self.full():
            task = self._loop.task()
            self._wait_not_full.push(task)
            await self._loop.switch_coro()

        self._put(item)

    def _get(self) -> T:
        item = self._items.popleft()
        if self._wait_not_full:
            task = self._wait_not_full.pop()
            self._loop.call_soon(task, value=None)
        return item

    def try_get(self) -> tuple[bool, T | None]:
        """Nonblocking get: Return True if a get attempt is successful."""
        if self.empty():
            return False, None
        return True, self._get()

    async def get(self) -> T:
        """Block until an item is available to get."""
        if self.empty():
            task = self._loop.task()
            self._wait_not_empty.push(task)
            await self._loop.switch_coro()

        return self._get()
