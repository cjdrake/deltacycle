"""Queue synchronization primitive."""

# pylint: disable=protected-access

from collections import deque
from typing import Any

from ._loop_if import LoopIf
from ._suspend_resume import SuspendResume
from ._task import TaskState, WaitFifo


class Queue(LoopIf):
    """TODO(cjdrake): Write docstring."""

    def __init__(self, maxsize: int = 0):
        self._maxsize = maxsize
        self._items: deque[Any] = deque()
        self._wait_not_empty = WaitFifo()
        self._wait_not_full = WaitFifo()

    @property
    def maxsize(self) -> int:
        return self._maxsize

    # def __len__(self) -> int:
    #    return len(self._items)

    def empty(self) -> bool:
        return not self._items

    def full(self) -> bool:
        return self._maxsize > 0 and len(self._items) == self._maxsize

    def _put(self, item: Any):
        self._items.append(item)
        if self._wait_not_empty:
            self._loop.call_soon(self._wait_not_empty.pop(), value=self)

    # def try_put(self, item: Any) -> bool:
    #    if self.full():
    #        return False
    #    self._put(item)
    #    return True

    async def put(self, item: Any):
        if self.full():
            task = self._loop.task()
            self._wait_not_full.push(task)
            task._set_state(TaskState.WAITING)
            await SuspendResume()

        self._put(item)

    def _get(self) -> Any:
        item = self._items.popleft()
        if self._wait_not_full:
            self._loop.call_soon(self._wait_not_full.pop(), value=self)
        return item

    # def try_get(self) -> tuple[bool, Any]:
    #    if self.empty():
    #        return False, None
    #    return True, self._get()

    async def get(self) -> Any:
        if self.empty():
            task = self._loop.task()
            self._wait_not_empty.push(task)
            task._set_state(TaskState.WAITING)
            await SuspendResume()

        return self._get()
