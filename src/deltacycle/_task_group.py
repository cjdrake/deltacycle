"""Task Group"""

from __future__ import annotations

from collections.abc import Coroutine
from types import TracebackType
from typing import Any

from ._loop_if import LoopIf
from ._task import Task, TaskState


class TaskGroup(LoopIf):
    """Group of tasks."""

    def __init__(self):
        self._parent = self._loop.task()
        # Preserve child task order
        self._children: list[Task] = []
        self._done: list[Task] = []
        self._excs: list[Exception] = []

    async def __aenter__(self) -> TaskGroup:
        return self

    def _record(self, child: Task) -> bool:
        self._done.append(child)
        if child.state() in {TaskState.RESULTED, TaskState.CANCELLED}:
            return False
        if child.state() is TaskState.EXCEPTED:
            self._excs.append(child._exception)  # type: ignore
            return True
        assert False  # pragma: no cover

    async def __aexit__(
        self,
        exc_type: type[Exception] | None,
        exc: Exception | None,
        traceback: TracebackType | None,
    ):
        not_done: set[Task] = set()

        for child in self._children:
            if child.done():
                # NOTE: Ignore child exception
                _ = self._record(child)
            else:
                not_done.add(child)
                child._wait(self._parent)

        # Parent raised an exception
        if exc:
            # Cancel all children
            for child in not_done:
                child.cancel()
            while not_done:
                child: Task = await self._loop.switch_coro()
                not_done.remove(child)
                # NOTE: Ignore child exception
                _ = self._record(child)

            assert set(self._children) == set(self._done)

            # Suppress child exception(s)
            # Re-raise parent exception
            return False

        cancelled: set[Task] = set()

        # Parent did NOT raise an exception
        # Wait for children to complete
        while not_done:
            child: Task = await self._loop.switch_coro()
            not_done.remove(child)
            x = self._record(child)

            # If children spawn newborns, add them to the waiting set
            n = len(self._done) + len(not_done)
            for newborn in self._children[n:]:
                not_done.add(newborn)
                newborn._wait(self._parent)

            # If child raised an exception, cancel remaining siblings
            if x:
                for sibling in not_done - cancelled:
                    sibling.cancel()
                    cancelled.add(sibling)

        assert set(self._children) == set(self._done)

        # Re-raise child exception(s)
        if self._excs:
            raise ExceptionGroup("errors", self._excs)

    def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
        priority: int = 0,
    ) -> Task:
        task = self._loop.create_task(coro, name, priority)
        self._children.append(task)
        return task
