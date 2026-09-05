"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Any

from ._kernel_if import KernelIf
from ._task import Blocking, SupportsDropTask, Task


class _WaitQ(SupportsDropTask):
    """Tasks wait for event trigger."""

    def __init__(self):
        self._items: dict[Task[Any], None] = {}

    def drop(self, task: Task[Any]):
        del self._items[task]
        task._unlink(tq=self)

    def push(self, task: Task[Any]):
        task._link(tq=self)
        self._items[task] = None

    def pop(self) -> Iterator[Task[Any]]:
        tasks = list(self._items)
        for task in tasks:
            self.drop(task)
            yield task


class _BlockQ(SupportsDropTask):
    """Tasks wait for event trigger."""

    def __init__(self):
        self._items: dict[Task[Any], Event] = {}

    def drop(self, task: Task[Any]):
        del self._items[task]
        task._unlink(tq=self)

    def push(self, task: Task[Any], blk_event: Event):
        task._link(tq=self)
        self._items[task] = blk_event

    def pop(self) -> Iterator[tuple[Task[Any], Event]]:
        items = list(self._items.items())
        for task, blk_event in items:
            self.drop(task)
            yield task, blk_event


class Event(KernelIf, Blocking):
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
        self._blockq = _BlockQ()

    def __bool__(self) -> bool:
        """Return flag state."""
        return self._flag

    def set(self):
        """Set the flag. Stop blocking waiting tasks."""
        self._flag = True

        for task in self._waitq.pop():
            self._kernel.call_soon(task, args=(Task.Command.RESUME,))
        for task, blk_event in self._blockq.pop():
            self._kernel._forks.clr(task, blk_event)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, blk_event))

    def clear(self):
        """Clear the flag. Start blocking waiting tasks."""
        self._flag = False

    def __await__(self) -> Generator[None, None, None]:
        """Await event set."""
        if self._is_blocking():
            task = self._kernel._check_task()
            self._waitq.push(task)
            y = yield from self._kernel._suspend().__await__()
            assert y is None

    # Blocking
    def _is_blocking(self) -> bool:
        return not self._flag

    def _block(self, task: Task[Any]):
        self._blockq.push(task, blk_event=self)

    def _unblock(self, task: Task[Any]):
        self._blockq.drop(task)
