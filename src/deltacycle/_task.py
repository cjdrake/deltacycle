"""TODO(cjdrake): Write docstring."""

from collections.abc import Awaitable, Coroutine
from enum import IntEnum, auto
from typing import Any


class TaskState(IntEnum):
    """Task State.

    Transitions::

                   +---------------------+
                   |                     |
                   v                     |
        INIT -> PENDING -> RUNNING -> WAITING
                                   -> RETURNED
    """

    # Initialized
    INIT = auto()

    # Queued; not yet running
    PENDING = auto()

    # Currently running
    RUNNING = auto()

    # Suspended; waiting to resume
    WAITING = auto()

    # Done: returned a result
    RETURNED = auto()


class Task:
    """Coroutine wrapper."""

    def __init__(self, coro: Coroutine[Any, Any, Any], region: int = 0):
        self._coro = coro
        self._region = region
        self._parents: set[Awaitable] = set()
        self._state = TaskState.INIT
        self._result = None

    @property
    def coro(self) -> Coroutine[Any, Any, Any]:
        return self._coro

    @property
    def region(self) -> int:
        return self._region

    # def done(self) -> bool:
    #    return self._state == TaskState.RETURNED

    def add_parent(self, parent: Awaitable):
        self._parents.add(parent)

    def remove_parent(self, parent: Awaitable):
        self._parents.remove(parent)

    def set_state(self, state: TaskState):
        self._state = state

    def set_result(self, result):
        self._result = result
