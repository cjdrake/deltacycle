"""Kernel Interface

Allows easy access to global kernel for Event, Semaphore, Task, ...
Works around tricky circular import: Kernel => Task => Kernel.
"""


class KernelIf:
    @property
    def _kernel(self):
        from ._top import get_running_kernel  # noqa: PLC0415

        kernel = get_running_kernel()
        try:
            cached_kernel = getattr(self, "__cached_kernel")
        except AttributeError:
            setattr(self, "__cached_kernel", kernel)
        else:
            if cached_kernel != kernel:
                raise RuntimeError("Ambiguous kernel")
        return kernel
