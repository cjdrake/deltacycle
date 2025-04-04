"""Test basic loop functionality"""

import logging

import pytest

from deltacycle import irun, run, sleep

logger = logging.getLogger("deltacycle")


async def hello():
    await sleep(2)
    logger.info("Hello")
    await sleep(2)
    logger.info("World")
    return 42


def test_run():

    with pytest.raises(ValueError):
        run(coro=None)

    ret = run(coro=hello())
    assert ret == 42


def test_irun():

    g = irun(coro=None)
    with pytest.raises(ValueError):
        next(g)

    g = irun(coro=hello())
    try:
        while True:
            next(g)
    except StopIteration as e:
        assert e.value == 42
