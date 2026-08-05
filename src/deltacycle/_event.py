"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Any, Self, cast

from ._kernel_if import KernelIf
from ._task import Blocking, Sendable, SupportsDropTask, Task


class _WaitQ(SupportsDropTask):
    """Tasks wait for event trigger."""

    def __init__(self):
        self._items: dict[Task[Any], None] = {}

    def drop(self, task: Task[Any]):
        del self._items[task]
        task.unlink(tq=self)

    def push(self, task: Task[Any]):
        task.link(tq=self)
        self._items[task] = None

    def pop(self) -> Iterator[Task[Any]]:
        tasks = list(self._items)
        for task in tasks:
            self.drop(task)
            yield task


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
        self._waitq = _WaitQ()

    def _blocking(self) -> bool:
        return not self._flag

    def drop(self, task: Task[Any]):
        self._waitq.drop(task)

    def __await__(self) -> Generator[None, Self, Self]:
        """Await event set."""
        if self._blocking():
            task = self._kernel.check_task()
            self._waitq.push(task)
            e = cast(typ=Self, val=(yield from task.switch_gen()))
            assert e is self

        return self

    def __bool__(self) -> bool:
        """Return flag state."""
        return self._flag

    def set(self):
        """Set the flag. Stop blocking waiting tasks."""
        self._flag = True

        for task in self._waitq.pop():
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))

    def clear(self):
        """Clear the flag. Start blocking waiting tasks."""
        self._flag = False

    # Blocking
    def try_block(self, task: Task[Any]) -> bool:
        if self._blocking():
            self._waitq.push(task)
            return True
        return False

    def future(self) -> Event:
        return self
