"""Event synchronization primitive"""

from ._suspend_resume import SuspendResume


class Event:
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False

    @property
    def _loop(self):
        from ._sim import get_running_loop  # pylint: disable=import-outside-toplevel

        return get_running_loop()

    async def wait(self):
        if not self._flag:
            self._loop.fifo_wait(self)
            await SuspendResume()

    def set(self):
        self._loop.event_set(self)
        self._flag = True

    def clear(self):
        self._flag = False

    def is_set(self) -> bool:
        return self._flag
