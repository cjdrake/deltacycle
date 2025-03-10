"""TODO(cjdrake): Write docstring."""

from ._suspend_resume import SuspendResume


def _loop():
    from ._sim import get_running_loop  # pylint: disable=import-outside-toplevel

    return get_running_loop()


class Event:
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False

    async def wait(self):
        if not self._flag:
            loop = _loop()
            loop.fifo_wait(self)
            await SuspendResume()

    def set(self):
        loop = _loop()
        loop.event_set(self)
        self._flag = True

    def clear(self):
        self._flag = False

    def is_set(self) -> bool:
        return self._flag
