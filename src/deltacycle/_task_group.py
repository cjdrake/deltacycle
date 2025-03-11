"""Task Group"""

from collections.abc import Coroutine
from typing import Any

from ._loop_if import LoopIf
from ._task import Task


class TaskGroup(LoopIf):
    """Group of tasks."""

    def __init__(self):
        self._tasks: set[Task] = set()

    def create_task(self, coro: Coroutine[Any, Any, Any], region: int = 0) -> Task:
        task = self._loop.create_task(coro, region)
        self._tasks.add(task)
        return task

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        while self._tasks:
            task = self._tasks.pop()
            await task
