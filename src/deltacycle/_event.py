"""Event synchronization primitive"""

# pylint: disable=protected-access

from ._loop_if import LoopIf
from ._suspend_resume import SuspendResume
from ._task import TaskState, WaitFifo


class Event(LoopIf):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = WaitFifo()

    async def wait(self):
        if not self._flag:
            task = self._loop.task()
            self._waiting.push(task)
            task._set_state(TaskState.WAITING)
            await SuspendResume()

    def set(self):
        while self._waiting:
            self._loop.call_soon(self._waiting.pop(), value=self)
        self._flag = True

    def clear(self):
        self._flag = False

    def is_set(self) -> bool:
        return self._flag
