"""Hello, world!"""

# pyright: reportAttributeAccessIssue=false

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import Kernel, get_kernel, run, sleep

logger = logging.getLogger("deltacycle")


EXP = [
    (-1, "Before Time"),
    (2, "Hello"),
    (4, "World"),
]


def test_hello(caplog: LogCaptureFixture):
    """Test basic async/await hello world functionality."""
    caplog.set_level(logging.INFO, logger="deltacycle")

    logger.info("Before Time")

    async def hello():
        await sleep(2)
        logger.info("Hello")
        await sleep(2)
        logger.info("World")
        return 42

    ret = run(hello())
    assert ret == 42

    kernel = get_kernel()
    assert kernel is not None
    assert kernel.state() is Kernel.State.COMPLETED

    with pytest.raises(RuntimeError):
        run(kernel=kernel)

    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == EXP
