"""Hello, world!"""

import logging

import pytest

from deltacycle import InvalidStateError, LoopState, get_loop, run, sleep

logger = logging.getLogger("deltacycle")


EXP = [
    (2, "Hello"),
    (4, "World"),
]


def test_hello(caplog):
    """Test basic async/await hello world functionality."""
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def hello():
        await sleep(2)
        logger.info("Hello")
        await sleep(2)
        logger.info("World")
        return 42

    ret = run(hello())
    assert ret == 42

    loop = get_loop()
    assert loop is not None
    assert loop.state() is LoopState.COMPLETED

    with pytest.raises(InvalidStateError):
        run(loop=loop)

    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == EXP
