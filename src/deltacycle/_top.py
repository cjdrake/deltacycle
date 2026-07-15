"""Top-level functions."""

from collections.abc import Generator
from typing import Any

from ._kernel import DefaultKernel, Kernel
from ._task import Blocking, Sendable, Task, TaskCoro

_kernel: Kernel | None = None


def get_running_kernel() -> Kernel:
    """Return currently running kernel.

    May be used by a simulation task to access kernel state.

    Returns:
        Kernel instance.

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    if _kernel is None:
        raise RuntimeError("No kernel")
    if _kernel.state() is not Kernel.State.RUNNING:
        raise RuntimeError("Kernel not RUNNING")
    return _kernel


def get_kernel() -> Kernel | None:
    """Get the current kernel.

    DeltaCycle only supports one simulation kernel at a time.
    This function gets the handle to that kernel, which may be ``None``.

    May be used by high level code to manage multiple kernels.

    Returns:
        Kernel instance or ``None``.
    """
    return _kernel


def set_kernel(kernel: Kernel | None = None):
    """Set the current kernel.

    DeltaCycle only supports one simulation kernel at a time.
    This function sets the handle to that kernel, which may be ``None``.

    May be used by high level code to manage multiple kernels.

    Args:
        kernel: Kernel instance or ``None``.
    """
    global _kernel  # noqa: PLW0603
    _kernel = kernel


def _get_kt() -> tuple[Kernel, Task | None]:
    kernel = get_running_kernel()
    task = kernel.task()
    return kernel, task


def get_current_task() -> Task | None:
    """Return currently running task.

    Returns:
        Task instance.

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    _, task = _get_kt()
    return task


def create_task[ResultType](
    coro: TaskCoro[ResultType],
    name: str | None = None,
    **kwargs: Any,
) -> Task[ResultType]:
    """Create a task, and schedule it to start soon.

    Args:
        coro: Coroutine function instance.
        name: Identify the task for logging/debugging purposes.
            If not given, a default name like ``Task-{index}`` will be assigned.
            Not guaranteed to be unique.
        kwargs: Arguments passed to the kernel to customize task execution.

    Returns:
        Created Task instance.

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    kernel = get_running_kernel()
    return kernel.create_task(coro, name, **kwargs)


def now() -> int:
    """Return current simulation time.

    Returns:
        Current simulation time.

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    kernel = get_running_kernel()
    return kernel.time()


def _run_pre[MainResultType](
    coro: TaskCoro[MainResultType] | None,
    kernel: Kernel[MainResultType] | None,
    kernel_type: type[Kernel[MainResultType]],
) -> Kernel[MainResultType]:
    if kernel is None:
        if coro is None:
            raise ValueError("New kernel requires a valid coro arg")
        kernel = kernel_type(coro)
        set_kernel(kernel)
    else:
        set_kernel(kernel)

    return kernel


def run[MainResultType](
    coro: TaskCoro[MainResultType] | None = None,
    kernel: Kernel[MainResultType] | None = None,
    kernel_type: type[Kernel[MainResultType]] = DefaultKernel,
    ticks: int | None = None,
    until: int | None = None,
) -> MainResultType | None:
    """Run a simulation.

    If a simulation hits the run limit, it will exit and return ``None``.
    That simulation may be resumed any number of times.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Main coroutine function instance.
            Required if creating a new kernel.
            Ignored if using an existing kernel.
        kernel: Optional Kernel instance.
            If not provided, a new kernel will be created.
        ticks: Optional relative run limit.
            If provided, run for *ticks* simulation time steps.
        until: Optional absolute run limit.
            If provided, run *until* specified simulation time.

    Returns:
        If the main coroutine runs until completion, return its result.
        Otherwise, return ``None``.

    Raises:
        ValueError: Creating a new kernel, but no main coroutine provided.
        RuntimeError: The kernel is in an invalid state.
    """
    kernel = _run_pre(coro, kernel, kernel_type)
    kernel(ticks, until)

    if kernel.main.done():
        return kernel.main.result()


def step[MainResultType](
    coro: TaskCoro[MainResultType] | None = None,
    kernel: Kernel[MainResultType] | None = None,
    kernel_type: type[Kernel[MainResultType]] = DefaultKernel,
) -> Generator[int, None, MainResultType | None]:
    """Step (iterate) a simulation.

    Iterated simulations do not have a run limit.
    It is the user's responsibility to break at the desired time.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Main coroutine function instance.
            Required if creating a new kernel.
            Ignored if using an existing kernel.
        kernel: Optional Kernel instance.
            If not provided, a new kernel will be created.

    Yields:
        Time immediately *before* the next time slot executes.

    Returns:
        Main coroutine result.

    Raises:
        ValueError: Creating a new kernel, but no main coroutine provided.
        RuntimeError: The kernel is in an invalid state.
    """
    kernel = _run_pre(coro, kernel, kernel_type)
    yield from kernel

    if kernel.main.done():
        return kernel.main.result()


async def sleep(delay: int):
    """Suspend the current task, and wake up after a delay."""
    if delay < 0:
        raise ValueError(f"Expected delay ≥ 0, got {delay}")
    kernel, task = _get_kt()
    assert task is not None
    kernel.call_later(delay, task, args=(Task.Command.RESUME,))
    y = await task.switch_coro()
    assert y is None


async def all_of(fst: Blocking, *rst: Blocking) -> tuple[Sendable, ...]:
    """Block forward progress until all items are unblocked.

    Args:
        fst, rst: Sequence of blocking items.

    Returns:
        Tuple of items in unblocking order.
    """
    args = (fst,) + rst
    # Uniquify
    bs = list(dict.fromkeys(args))

    kernel, task = _get_kt()
    assert task is not None

    while True:
        blocked: list[Sendable] = []
        unblocked: list[Sendable] = []

        for b in bs:
            if b.try_block(task):
                blocked.append(b.future())
            else:
                unblocked.append(b.future())

        if not blocked:
            return tuple(unblocked)

        kernel.fork(task, *blocked)
        await task.switch_coro()


async def any_of(fst: Blocking, *rst: Blocking) -> Sendable:
    """Block forward progress until at least one item is unblocked.

    Args:
        fst, rst: Sequence of blocking items.

    Returns:
        Item that unblocked first.
    """
    args = (fst,) + rst
    # Uniquify
    bs = list(dict.fromkeys(args))

    kernel, task = _get_kt()
    assert task is not None

    blocked: list[Sendable] = []

    for b in bs:
        if b.try_block(task):
            blocked.append(b.future())
        else:
            while blocked:
                x = blocked.pop()
                x.wait_drop(task)
            return b.future()

    kernel.fork(task, *blocked)
    x = await task.switch_coro()
    assert x is not None
    return x
