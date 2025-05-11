"""Suspend / Resume"""

from collections.abc import Awaitable, Generator
from typing import Any


class SuspendResume(Awaitable[Any]):
    """Suspend/Resume current task.

    Use case:
    1. Current task A suspends itself: RUNNING => WAITING
    2. Event loop chooses PENDING tasks ..., T
    3. ... Task T wakes up task A w/ value X: WAITING => PENDING
    4. Event loop chooses PENDING tasks ..., A: PENDING => RUNNING
    5. Task A resumes with value X

    The value X can be used to pass information to the task.
    """

    def __await__(self) -> Generator[None, Any, Any]:
        # Suspend
        value = yield
        # Resume
        return value
