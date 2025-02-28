"""TODO(cjdrake): Write docstring."""

from collections.abc import Awaitable, Generator
from typing import Any


class SuspendResume(Awaitable):
    """Suspend/Resume execution of the current task."""

    def __await__(self) -> Generator[None, Any, Any]:
        # Suspend
        value: Any = yield
        # Resume
        return value
