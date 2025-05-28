"""Task Group"""

from collections.abc import Coroutine
from types import TracebackType
from typing import Any

from ._loop_if import LoopIf
from ._task import Task, TaskState


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
        traceback: TracebackType | None,
    ):
        # Prune children that are already done
        children = {c for c in self._children if not c.done()}

        for child in children:
            # Child completes => Parent resumes
            child._wait(self._parent)

        # An exception was raised in the group body
        if exc:
            # Cancel all children
            for child in children:
                child.cancel()
            for child in children:
                await self._loop.switch_coro()
            # Do NOT suppress the exception
            return False

        child_excs: list[Exception] = []

        # Run all children
        while children:
            # Child 1) returns, 2) is cancelled, or 3) raises exception
            child: Task = await self._loop.switch_coro()
            children.remove(child)

            # If child raises an exception, cancel remaining siblings
            if child.state() is TaskState.EXCEPTED:
                if not child_excs:
                    for sibling in children:
                        sibling.cancel()
                assert child._exception is not None
                child_excs.append(child._exception)

        # Re-raise child exception
        if child_excs:
            raise ExceptionGroup("errors", child_excs)
