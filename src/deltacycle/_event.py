"""Event synchronization primitive"""

from ._loop_if import LoopIf
from ._task import WaitFifo


class Event(LoopIf):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = WaitFifo()

    async def wait(self):
        if not self._flag:
            task = self._loop.task()
            self._waiting.push(task)
            await self._loop.switch_coro()

    def set(self):
        while self._waiting:
            task = self._waiting.pop()
            self._loop.call_soon(task, value=self)
        self._flag = True

    def clear(self):
        self._flag = False

    def is_set(self) -> bool:
        return self._flag
