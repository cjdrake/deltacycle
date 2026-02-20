"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Generator
from typing import Self

from ._kernel_if import KernelIf
from ._task import Blocking, EventQ, Sendable, Task


class Event(KernelIf, Blocking, Sendable):
    """Notify multiple tasks that some event has happened.

    An event instance is lightweight.
    It consists of a flag, and a FIFO of waiting tasks.

    When the event is created, its flag defaults to ``False``.
    In this state, the event will block all tasks that await it.
    When a task invokes the event's ``set`` method,
    that sets the flag (to ``True``), and unblocks all waiting tasks.

    If the event's flag is set, it will not block awaiting tasks.
    When a task invokes the event's ``clear`` method,
    that clears the flag (to ``False``),
    and the event will go back to blocking awaiting tasks.
    """

    def __init__(self):
        self._flag = False
        self._waiting = EventQ()

    def _blocking(self) -> bool:
        return not self._flag

    def wait_push(self, task: Task):
        self._waiting.push(task)

    def wait_drop(self, task: Task):
        self._waiting.drop(task)

    def __await__(self) -> Generator[None, Sendable, Self]:
        """Await event set."""
        if self._blocking():
            task = self._kernel.task()
            self.wait_push(task)
            e = yield from task.switch_gen()
            assert e is self

        return self

    def __bool__(self) -> bool:
        """Return flag state."""
        return self._flag

    def set(self):
        """Set the flag. Stop blocking waiting tasks."""
        self._flag = True
        self._waiting.load()

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))

    def clear(self):
        """Clear the flag. Start blocking waiting tasks."""
        self._flag = False

    # Blocking
    def try_block(self, task: Task) -> bool:
        if self._blocking():
            self.wait_push(task)
            return True
        return False

    @property
    def x(self) -> Event:
        return self
