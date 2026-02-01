"""KernelIf abstract base class

Allows easy access to global kernel for Event, Semaphore, Task, ...
Works around tricky circular import: Kernel => Task => Kernel.
"""

from functools import cached_property


class KernelIf:
    @cached_property
    def _kernel(self):
        from ._top import get_running_kernel  # noqa: PLC0415

        return get_running_kernel()
