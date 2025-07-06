"""Top-level functions."""

from collections.abc import Generator
from typing import Any

from ._event import Event
from ._loop import Loop, LoopState
from ._task import Predicate, Task, TaskCommand, TaskCoro
from ._variable import Variable

# yields time: int; returns main.result()
type LoopGen = Generator[int, None, Any]

_loop: Loop | None = None


def get_running_loop() -> Loop:
    """Return currently running loop.

    Returns:
        Loop instance

    Raises:
        RuntimeError: No loop, or loop is not currently running.
    """
    if _loop is None:
        raise RuntimeError("No loop")
    if _loop.state() is not LoopState.RUNNING:
        raise RuntimeError("Loop not RUNNING")
    return _loop


def get_loop() -> Loop | None:
    """Get the current event loop."""
    return _loop


def set_loop(loop: Loop | None = None):
    """Set the current event loop."""
    global _loop  # noqa: PLW0603
    _loop = loop


def get_current_task() -> Task:
    """Return currently running task.

    Returns:
        Task instance

    Raises:
        RuntimeError: No loop, or loop is not currently running.
    """
    loop = get_running_loop()
    return loop.task()


def create_task(
    coro: TaskCoro,
    name: str | None = None,
    priority: int = 0,
) -> Task:
    """Create a task, and schedule it to start soon."""
    loop = get_running_loop()
    return loop.create_task(coro, name, priority)


def now() -> int:
    """Return current simulation time.

    Returns:
        int time

    Raises:
        RuntimeError: No loop, or loop is not currently running.
    """
    loop = get_running_loop()
    return loop.time()


def _run_pre(coro: TaskCoro | None, loop: Loop | None) -> Loop:
    if loop is None:
        loop = Loop()
        set_loop(loop)
        if coro is None:
            raise ValueError("New loop requires a valid coro arg")
        assert coro is not None
        loop.create_main(coro)
    else:
        set_loop(loop)

    return loop


def run(
    coro: TaskCoro | None = None,
    loop: Loop | None = None,
    ticks: int | None = None,
    until: int | None = None,
) -> Any:
    """Run a simulation.

    If a simulation hits the run limit, it will exit and return None.
    That simulation may be resumed any number of times.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Optional main coroutine.
            Required if creating a new loop.
            Ignored if using an existing loop.
        loop: Optional Loop instance.
            If not provided, a new loop will be created.
        ticks: Optional relative run limit.
            If provided, run for *ticks* simulation time steps.
        until: Optional absolute run limit.
            If provided, run until *ticks* simulation time steps.

    Returns:
        If the main coroutine runs til completion, return its result.
        Otherwise, return ``None``.

    Raises:
        ValueError: Creating a new loop, but no coro provided.
        TypeError: ticks and until args conflict.
        RuntimeError: The loop is in an invalid state.
    """
    loop = _run_pre(coro, loop)
    loop(ticks, until)

    if loop.main.done():
        return loop.main.result()


def irun(coro: TaskCoro | None = None, loop: Loop | None = None) -> LoopGen:
    """Iterate a simulation.

    Iterated simulations do not have a run limit.
    It is the user's responsibility to break at the desired time.
    If all tasks are exhausted, return the main coroutine result.

    Args:
        coro: Optional main coroutine.
            Required if creating a new loop.
            Ignored if using an existing loop.
        loop: Optional Loop instance.
            If not provided, a new loop will be created.

    Yields:
        int time immediately *before* the next time slot executes.

    Returns:
        main coroutine result.

    Raises:
        ValueError: Creating a new loop, but no coro provided.
        TypeError: ticks and until args conflict.
        RuntimeError: The loop is in an invalid state.
    """
    loop = _run_pre(coro, loop)
    yield from loop

    assert loop.main.done()
    return loop.main.result()


async def sleep(delay: int):
    """Suspend the task, and wake up after a delay."""
    loop = get_running_loop()
    task = loop.task()
    loop.call_later(delay, task, value=(TaskCommand.RESUME, None))
    await loop.switch_coro()


async def any_event(*events: Event) -> Event:
    """Resume execution after first event.

    Suspend execution of the current task;
    Resume after any event in the sensitivity list,

    Args:
        events: Tuple of Event, a sensitivity list.

    Returns:
        The Event instance that triggered the task to resume.
    """
    loop = get_running_loop()
    task = loop.task()

    # Search for first set event
    fst = None
    for e in events:
        if e:
            fst = e
            break

    # No events set yet
    if fst is None:
        # Await first event to be set
        for e in events:
            e._wait(task)
        fst = await loop.switch_coro()
        assert isinstance(fst, Event)

    return fst


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
    loop = get_running_loop()
    task = loop.task()
    for v, p in vps.items():
        v._wait(p, task)
    v: Variable = await loop.switch_coro()
    return v
