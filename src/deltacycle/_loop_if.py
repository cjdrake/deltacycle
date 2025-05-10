"""LoopIf abstract base class

Allows easy access to global event loop for Event, Semaphore, Task, ...
Works around tricky circular import: Loop => Task => Loop.
"""

# pylint: disable=import-outside-toplevel

from abc import ABC
from functools import cached_property


class LoopIf(ABC):
    @cached_property
    def _loop(self):
        from ._loop import get_running_loop

        return get_running_loop()
