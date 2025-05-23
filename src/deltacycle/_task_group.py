"""Task Group"""

from collections.abc import Coroutine
from types import TracebackType
from typing import Any

from ._loop_if import LoopIf
from ._suspend_resume import SuspendResume
from ._task import Task


class TaskGroup(LoopIf):
    """Group of tasks."""

    def __init__(self):
        self._children: set[Task] = set()

    def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
        priority: int = 0,
    ) -> Task:
        parent = self._loop.task()
        child = self._loop.create_task(coro, name, priority)
        self._children.add(child)
        child._wait(parent)
        return child

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type: type[Exception], exc: Exception, tb: TracebackType):
        done: set[Task] = set()

        while True:
            child = await SuspendResume()
            done.add(child)

            # TODO(cjdrake): Handle exceptions

            if done == self._children:
                break
