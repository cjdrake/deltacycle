"""Top-level functions."""

from collections.abc import Generator
from typing import Any

from ._kernel import Kernel
from ._task import Task, TaskCoro
from ._variable import Predicate, Variable

_kernel: Kernel | None = None


def get_running_kernel() -> Kernel:
    """Return currently running kernel.

    Returns:
        Kernel instance

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    if _kernel is None:
        raise RuntimeError("No kernel")
    if _kernel.state() is not Kernel.State.RUNNING:
        raise RuntimeError("Kernel not RUNNING")
    return _kernel


def get_kernel() -> Kernel | None:
    """Get the current kernel."""
    return _kernel


def set_kernel(kernel: Kernel | None = None):
    """Set the current kernel."""
    global _kernel  # noqa: PLW0603
    _kernel = kernel


def _get_kt() -> tuple[Kernel, Task]:
    kernel = get_running_kernel()
    task = kernel.task()
    return kernel, task


def get_current_task() -> Task:
    """Return currently running task.

    Returns:
        Task instance

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    _, task = _get_kt()
    return task


def create_task(
    coro: TaskCoro,
    name: str | None = None,
    priority: int = 0,
) -> Task:
    """Create a task, and schedule it to start soon."""
    kernel = get_running_kernel()
    return kernel.create_task(coro, name, priority)


def now() -> int:
    """Return current simulation time.

    Returns:
        int time

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    kernel = get_running_kernel()
    return kernel.time()


def _run_pre(coro: TaskCoro | None, kernel: Kernel | None) -> Kernel:
    if kernel is None:
        kernel = Kernel()
        set_kernel(kernel)
        if coro is None:
            raise ValueError("New kernel requires a valid coro arg")
        assert coro is not None
        kernel.create_main(coro)
    else:
        set_kernel(kernel)

    return kernel


def run(
    coro: TaskCoro | None = None,
    kernel: Kernel | None = None,
    ticks: int | None = None,
    until: int | None = None,
) -> Any:
    """Run a simulation.

    If a simulation hits the run limit, it will exit and return None.
    That simulation may be resumed any number of times.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Optional main coroutine.
            Required if creating a new kernel.
            Ignored if using an existing kernel.
        kernel: Optional Kernel instance.
            If not provided, a new kernel will be created.
        ticks: Optional relative run limit.
            If provided, run for *ticks* simulation time steps.
        until: Optional absolute run limit.
            If provided, run until *ticks* simulation time steps.

    Returns:
        If the main coroutine runs til completion, return its result.
        Otherwise, return ``None``.

    Raises:
        ValueError: Creating a new kernel, but no coro provided.
        TypeError: ticks and until args conflict.
        RuntimeError: The kernel is in an invalid state.
    """
    kernel = _run_pre(coro, kernel)
    kernel(ticks, until)

    if kernel.main.done():
        return kernel.main.result()


def step(
    coro: TaskCoro | None = None,
    kernel: Kernel | None = None,
) -> Generator[int, None, Any]:
    """Step (iterate) a simulation.

    Iterated simulations do not have a run limit.
    It is the user's responsibility to break at the desired time.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Optional main coroutine.
            Required if creating a new kernel.
            Ignored if using an existing kernel.
        kernel: Optional Kernel instance.
            If not provided, a new kernel will be created.

    Yields:
        int time immediately *before* the next time slot executes.

    Returns:
        main coroutine result.

    Raises:
        ValueError: Creating a new kernel, but no coro provided.
        TypeError: ticks and until args conflict.
        RuntimeError: The kernel is in an invalid state.
    """
    kernel = _run_pre(coro, kernel)
    yield from kernel

    assert kernel.main.done()
    return kernel.main.result()


async def sleep(delay: int):
    """Suspend the task, and wake up after a delay."""
    kernel, task = _get_kt()
    kernel.call_later(delay, task, args=(Task.Command.RESUME,))
    y = await kernel.switch_coro()
    assert y is None


async def any_var(vps: dict[Variable, Predicate]) -> Variable:
    """Resume execution upon predicated variable change.

    Suspend execution of the current task;
    Resume when any variable in the sensitivity list changes,
    *and* the predicate function evaluates to True.
    If the predicate function is None, it will default to *any* change.

    Args:
        vps: Dict of Variable => Predicate mappings, a sensitivity list.

    Returns:
        The Variable instance that triggered the task to resume.
    """
    kernel, task = _get_kt()

    for v, p in vps.items():
        v.wait_for(p, task)
        kernel.add_task_sched(task, v)
    v = await kernel.switch_coro()
    assert isinstance(v, Variable)
    return v
