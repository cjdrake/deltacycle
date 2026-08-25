"""Test basic kernel functionality"""

import pytest

from deltacycle import (
    Event,
    Kernel,
    create_task,
    get_kernel,
    get_running_kernel,
    run,
    set_kernel,
    sleep,
    step,
)

from .conftest import Trace, trace


async def main(n: int):
    for i in range(n):
        trace(f"{i}")
        await sleep(1)
    return n


def test_run(captrace: Trace):
    ret = run(main(42))
    assert ret == 42

    assert captrace == {(i, "main", str(i)) for i in range(42)}


def test_irun(captrace: Trace):
    g = step(main(42))
    try:
        while True:
            next(g)
    except StopIteration as e:
        assert e.value == 42

    assert captrace == {(i, "main", str(i)) for i in range(42)}


def test_cannot_run(captrace: Trace):
    run(main(100))
    kernel = get_kernel()

    # Kernel is already in COMPLETED state
    with pytest.raises(RuntimeError):
        run(kernel=kernel)

    with pytest.raises(RuntimeError):
        list(step(kernel=kernel))


def test_limits(captrace: Trace):
    run(main(1000), ticks=51)
    kernel = get_running_kernel()
    assert kernel.time() == 50

    run(kernel=kernel, ticks=51)
    assert kernel.time() == 100

    run(kernel=kernel, until=201)
    assert kernel.time() == 200

    # Both ticks & until: first limit to hit
    run(kernel=kernel, ticks=101, until=302)
    assert kernel.time() == 300
    run(kernel=kernel, ticks=102, until=401)
    assert kernel.time() == 400

    with pytest.raises(ValueError):
        run(kernel=kernel, ticks=-1)
    with pytest.raises(ValueError):
        run(kernel=kernel, ticks=0, until=-1)


def test_nocoro():
    with pytest.raises(ValueError):
        run()
    with pytest.raises(ValueError):
        list(step())  # pyright: ignore[reportUnknownArgumentType]


def test_get_running_kernel(captrace: Trace):
    # No kernel
    set_kernel()
    with pytest.raises(RuntimeError):
        get_running_kernel()

    # Kernel is not running
    run(main(42))
    with pytest.raises(RuntimeError):
        get_running_kernel()


def test_ambiguous_kernel():
    e = Event()

    async def sleep_set(t: int, e: Event):
        await sleep(t)
        e.set()

    async def main():
        create_task(sleep_set(10, e))
        await e
        e.clear()

    # Use Event object with new kernel
    run(main())

    # Use *same* Event object with different kernel
    with pytest.raises(RuntimeError):
        run(main())


def test_keyboard_interrupt_exits():
    async def main():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run(main())
    kernel = get_kernel()
    assert kernel is not None
    assert kernel.state() is Kernel.State.EXITED
