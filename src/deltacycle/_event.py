"""Event synchronization primitive"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Any, Self

from ._kernel_if import KernelIf
from ._task import Blocking, SupportsDropTask, Task


class _WaitQ(SupportsDropTask):
    """Tasks wait for event trigger."""

    def __init__(self):
        self._items: dict[Task[Any], Event | None] = {}

    def drop(self, task: Task[Any]):
        del self._items[task]
        task._unlink(tq=self)

    def push(self, task: Task[Any], event: Event | None):
        task._link(tq=self)
        self._items[task] = event

    def pop(self) -> Iterator[tuple[Task[Any], Event | None]]:
        items = list(self._items.items())
        for task, event in items:
            self.drop(task)
            yield task, event


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

    def __bool__(self) -> bool:
        """Return flag state."""
        return self._flag

    def set(self):
        """Set the flag. Stop blocking waiting tasks."""
        self._flag = True

        for task, event in self._waitq.pop():
            if event is not None:
                self._kernel._forks.clr(task, event)
                self._kernel.call_soon(task, args=(Task.Command.RESUME, event))
            else:
                self._kernel.call_soon(task, args=(Task.Command.RESUME,))

    def clear(self):
        """Clear the flag. Start blocking waiting tasks."""
        self._flag = False

    def __await__(self) -> Generator[None, Self, None]:
        """Await event set."""
        if self._is_blocking():
            task = self._kernel._check_task()
            self._waitq.push(task, event=None)
            y = yield from task._switch_gen()
            assert y is None

    # Blocking
    def _is_blocking(self) -> bool:
        return not self._flag

    def _unblock(self, task: Task[Any]):
        self._waitq.drop(task)

    def _do_block(self, task: Task[Any]):
        self._waitq.push(task, event=self)
