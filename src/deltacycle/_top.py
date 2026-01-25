"""Top-level functions."""

from collections import deque
from collections.abc import Generator
from typing import Any

from ._kernel import Kernel
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


def _get_kt() -> tuple[Kernel, Task]:
    kernel = get_running_kernel()
    task = kernel.task()
    return kernel, task


def get_current_task() -> Task:
    """Return currently running task.

    Returns:
        Task instance.

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
    """Create a task, and schedule it to start soon.

    Args:
        coro: Coroutine function instance.
        name: Identify the task for logging/debugging purposes.
            If not given, a default name like ``Task-{index}`` will be assigned.
            Not guaranteed to be unique.
        priority: Specify task execution order within the same timeslot.
            A lower number indicates higher priority.

    Returns:
        Created Task instance.

    Raises:
        RuntimeError: No kernel, or kernel is not currently running.
    """
    kernel = get_running_kernel()
    return kernel.create_task(coro, name, priority)


def now() -> int:
    """Return current simulation time.

    Returns:
        Current simulation time.

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
            If provided, run until *ticks* simulation time steps.

    Returns:
        If the main coroutine runs til completion, return its result.
        Otherwise, return ``None``.

    Raises:
        ValueError: Creating a new kernel, but no main coroutine provided.
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
    kernel = _run_pre(coro, kernel)
    yield from kernel

    assert kernel.main.done()
    return kernel.main.result()


async def sleep(delay: int):
    """Suspend the current task, and wake up after a delay."""
    kernel, task = _get_kt()
    kernel.call_later(delay, task, args=(Task.Command.RESUME,))
    y = await task.switch_coro()
    assert y is None


async def all_of(*bs: Blocking) -> tuple[Sendable, ...]:
    """Block forward progress until all items are unblocked.

    Args:
        bs: Sequence of blocking items.

    Returns:
        Return a tuple of items in unblocking order.
    """
    _, task = _get_kt()

    blocked: set[Sendable] = set()
    unblocked: deque[Sendable] = deque()

    for b in bs:
        if b.try_block(task):
            blocked.add(b.s)
        else:
            unblocked.append(b.s)

    while blocked:
        s = await task.switch_coro()
        assert isinstance(s, Sendable)
        blocked.remove(s)
        unblocked.append(s)

    return tuple(unblocked)


async def any_of(*bs: Blocking) -> Sendable | None:
    """Block forward progress until at least one item is unblocked.

    Args:
        bs: Sequence of blocking items.

    Returns:
        If the input is empty, return ``None``.
        Otherwise, return the item that unblocked first.
    """
    if not bs:
        return None

    kernel, task = _get_kt()

    blocked: set[Sendable] = set()

    for b in bs:
        if b.try_block(task):
            blocked.add(b.s)
        else:
            while blocked:
                s = blocked.pop()
                s.wait_drop(task)
            return b.s

    kernel.fork(task, *blocked)
    s = await task.switch_coro()
    assert isinstance(s, Sendable)
    return s
