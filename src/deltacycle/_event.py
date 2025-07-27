"""Event synchronization primitive"""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Generator
from typing import Self

from ._kernel_if import KernelIf
from ._task import Blocking, Cancelable, Task, TaskQueue


class _WaitQ(TaskQueue):
    """Tasks wait for variable touch."""

    def __init__(self):
        self._tasks: OrderedDict[Task, None] = OrderedDict()
        self._items: deque[Task] = deque()

    def __bool__(self) -> bool:
        return bool(self._items)

    def push(self, item: Task):
        item._link(self)
        self._tasks[item] = None

    def pop(self) -> Task:
        task = self._items.popleft()
        self.drop(task)
        return task

    def drop(self, task: Task):
        del self._tasks[task]
        task._unlink(self)

    def load(self):
        assert not self._items
        self._items.extend(self._tasks)


class Event(KernelIf, Blocking, Cancelable):
    """Notify multiple tasks that some event has happened."""

    def __init__(self):
        self._flag = False
        self._waiting = _WaitQ()

    def _blocking(self) -> bool:
        return not self._flag

    def wait_push(self, task: Task):
        self._waiting.push(task)

    def __await__(self) -> Generator[None, Cancelable, Self]:
        if self._blocking():
            task = self._kernel.task()
            self.wait_push(task)
            e = yield from self._kernel.switch_gen()
            assert e is self

        return self

    def try_block(self, task: Task) -> bool:
        if self._blocking():
            self.wait_push(task)
            return True
        return False

    @property
    def c(self) -> Event:
        return self

    def cancel(self, task: Task):
        self._waiting.drop(task)

    def __bool__(self) -> bool:
        return self._flag

    def set(self):
        self._flag = True
        self._waiting.load()

        while self._waiting:
            task = self._waiting.pop()
            self._kernel.join_any(task, self)
            self._kernel.call_soon(task, args=(Task.Command.RESUME, self))

    def clear(self):
        self._flag = False
