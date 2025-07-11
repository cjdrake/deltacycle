"""Test basic kernel functionality"""

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import get_kernel, get_running_kernel, run, set_kernel, sleep, step

logger = logging.getLogger("deltacycle")


async def main(n: int):
    for i in range(n):
        logger.info("%d", i)
        await sleep(1)
    return n


def test_run(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    ret = run(main(42))
    assert ret == 42

    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == [(i, str(i)) for i in range(42)]


def test_irun(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    g = step(main(42))
    try:
        while True:
            next(g)
    except StopIteration as e:
        assert e.value == 42

    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == [(i, str(i)) for i in range(42)]


def test_cannot_run(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    run(main(100))
    kernel = get_kernel()

    # Kernel is already in COMPLETED state
    with pytest.raises(RuntimeError):
        run(kernel=kernel)

    with pytest.raises(RuntimeError):
        list(step(kernel=kernel))


def test_limits(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

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

    with pytest.raises(TypeError):
        run(kernel=kernel, ticks=101.0, until=501)  # pyright: ignore[reportArgumentType]
    with pytest.raises(TypeError):
        run(kernel=kernel, ticks=101, until=501.0)  # pyright: ignore[reportArgumentType]


def test_nocoro():
    with pytest.raises(ValueError):
        run()
    with pytest.raises(ValueError):
        list(step())


def test_get_running_kernel():
    # No kernel
    set_kernel()
    with pytest.raises(RuntimeError):
        get_running_kernel()

    # Kernel is not running
    run(main(42))
    with pytest.raises(RuntimeError):
        get_running_kernel()
