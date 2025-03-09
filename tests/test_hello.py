"""Hello, world!"""

import logging

from deltacycle import run, sleep

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

    run(hello())

    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == EXP
