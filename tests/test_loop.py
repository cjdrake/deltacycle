"""Test basic loop functionality"""

import logging

import pytest

from deltacycle import get_loop, get_running_loop, irun, run, set_loop, sleep

logger = logging.getLogger("deltacycle")


async def main(n: int):
    for i in range(n):
        logger.info("%d", i)
        await sleep(1)
    return n


def test_run(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    ret = run(main(42))
    assert ret == 42

    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == [(i, str(i)) for i in range(42)]


def test_irun(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    g = irun(main(42))
    try:
        while True:
            next(g)
    except StopIteration as e:
        assert e.value == 42

    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == [(i, str(i)) for i in range(42)]


def test_cannot_run(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    run(main(100))
    loop = get_loop()

    # Loop is already in COMPLETED state
    with pytest.raises(RuntimeError):
        run(loop=loop)

    with pytest.raises(RuntimeError):
        list(irun(loop=loop))


def test_limits(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    run(main(1000), ticks=51)
    loop = get_running_loop()
    assert loop.time() == 50

    run(loop=loop, ticks=51)
    assert loop.time() == 100

    run(loop=loop, until=201)
    assert loop.time() == 200

    with pytest.raises(TypeError):
        run(loop=loop, ticks=42, until=42)


def test_nocoro():
    with pytest.raises(ValueError):
        run()
    with pytest.raises(ValueError):
        list(irun())


def test_get_running_loop():
    # No loop
    set_loop()
    with pytest.raises(RuntimeError):
        get_running_loop()

    # Loop is not running
    run(main(42))
    with pytest.raises(RuntimeError):
        get_running_loop()
