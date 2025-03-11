"""Event synchronization primitive"""

from ._loop_if import LoopIf
from ._suspend_resume import SuspendResume
from ._task import TaskState, WaitFifoIf


class Event(LoopIf, WaitFifoIf):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        WaitFifoIf.__init__(self)
        self._flag = False

    async def wait(self):
        if not self._flag:
            task = self._loop.task()
            self.push_task(task)
            task.set_state(TaskState.WAITING)
            await SuspendResume()

    def set(self):
        while self.has_task():
            task = self.pop_task()
            self._loop.call_soon(task, value=self)
        self._flag = True

    def clear(self):
        self._flag = False

    def is_set(self) -> bool:
        return self._flag
