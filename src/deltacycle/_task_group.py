"""Task Group"""

from collections.abc import Coroutine
from types import TracebackType
from typing import Any

from ._loop_if import LoopIf
from ._task import Task


class TaskGroup(LoopIf):
    """Group of tasks."""

    def __init__(self):
        self._parent = self._loop.task()
        self._children: list[Task] = []

    def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
        priority: int = 0,
    ) -> Task:
        task = self._loop.create_task(coro, name, priority)
        self._children.append(task)
        return task

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception] | None,
        exc: Exception | None,
        tb: TracebackType | None,
    ):
        # TODO(cjdrake): Handle this case
        assert exc_type is None and exc is None and tb is None

        not_done: set[Task] = set()

        for child in self._children:
            # TODO(cjdrake): Handle complete/cancelled/excepted tasks
            assert not child.done()
            not_done.add(child)
            # When child completes, immediately schedule parent
            child._wait(self._parent)

        while not_done:
            child: Task = await self._loop.switch_coro()
            not_done.remove(child)
            # TODO(cjdrake): Handle exceptions
