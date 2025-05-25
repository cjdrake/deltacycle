"""Queue synchronization primitive."""

from collections import deque
from collections.abc import Sized
from typing import Any

from ._loop_if import LoopIf
from ._task import WaitFifo


class Queue(Sized, LoopIf):
    """First-in, First-out (FIFO) queue."""

    def __init__(self, maxlen: int = 0):
        self._maxlen = maxlen
        self._items: deque[Any] = deque()
        self._wait_not_empty = WaitFifo()
        self._wait_not_full = WaitFifo()

    def __len__(self) -> int:
        return len(self._items)

    def empty(self) -> bool:
        return not self._items

    def full(self) -> bool:
        return self._maxlen > 0 and len(self._items) == self._maxlen

    def _put(self, item: Any):
        self._items.append(item)
        if self._wait_not_empty:
            self._loop.call_soon(self._wait_not_empty.pop(), value=self)

    def try_put(self, item: Any) -> bool:
        if self.full():
            return False
        self._put(item)
        return True

    async def put(self, item: Any):
        if self.full():
            task = self._loop.task()
            self._wait_not_full.push(task)
            # Task state: RUNNING => WAITING
            await self._loop.switch_coro()

        self._put(item)

    def _get(self) -> Any:
        item = self._items.popleft()
        if self._wait_not_full:
            self._loop.call_soon(self._wait_not_full.pop(), value=self)
        return item

    def try_get(self) -> tuple[bool, Any]:
        if self.empty():
            return False, None
        return True, self._get()

    async def get(self) -> Any:
        if self.empty():
            task = self._loop.task()
            self._wait_not_empty.push(task)
            # Task state: RUNNING => WAITING
            await self._loop.switch_coro()

        return self._get()
