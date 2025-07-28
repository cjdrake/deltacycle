"""Test deltacycle.CreditPool"""

# pyright: reportAttributeAccessIssue=false

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import CreditPool, create_task, run, sleep

logger = logging.getLogger("deltacycle")


def test_len():
    async def main():
        credits = CreditPool(capacity=10)
        assert len(credits) == 0
        credits.put(1)
        assert len(credits) == 1
        credits.put(2)
        assert len(credits) == 3
        assert credits
        await credits.get(1)
        assert len(credits) == 2
        await credits.get(2)
        assert len(credits) == 0
        assert not credits

    run(main())


async def use_get_put(credits: CreditPool, t1: int, t2: int):
    logger.info("enter")

    await sleep(t1)

    logger.info("attempt get")
    await credits.get(n=2)
    logger.info("acquired")

    try:
        await sleep(t2)
    finally:
        logger.info("put")
        credits.put(2)

    await sleep(10)
    logger.info("exit")


async def use_with(credits: CreditPool, t1: int, t2: int):
    logger.info("enter")

    await sleep(t1)

    logger.info("attempt get")
    async with credits.req(n=2):
        logger.info("acquired")
        await sleep(t2)
    logger.info("put")

    await sleep(10)
    logger.info("exit")


EXP1 = {
    # 0
    (0, "0", "enter"),
    (10, "0", "attempt get"),
    (10, "0", "acquired"),
    (20, "0", "put"),
    (30, "0", "exit"),
    # 1
    (0, "1", "enter"),
    (11, "1", "attempt get"),
    (11, "1", "acquired"),
    (21, "1", "put"),
    (31, "1", "exit"),
    # 2
    (0, "2", "enter"),
    (12, "2", "attempt get"),
    (12, "2", "acquired"),
    (22, "2", "put"),
    (32, "2", "exit"),
    # 3
    (0, "3", "enter"),
    (13, "3", "attempt get"),
    (13, "3", "acquired"),
    (23, "3", "put"),
    (33, "3", "exit"),
    # 4
    (0, "4", "enter"),
    (14, "4", "attempt get"),
    (14, "4", "acquired"),
    (24, "4", "put"),
    (34, "4", "exit"),
    # 5
    (0, "5", "enter"),
    (15, "5", "attempt get"),
    (20, "5", "acquired"),
    (30, "5", "put"),
    (40, "5", "exit"),
    # 6
    (0, "6", "enter"),
    (16, "6", "attempt get"),
    (21, "6", "acquired"),
    (31, "6", "put"),
    (41, "6", "exit"),
    # 7
    (0, "7", "enter"),
    (17, "7", "attempt get"),
    (22, "7", "acquired"),
    (32, "7", "put"),
    (42, "7", "exit"),
    # 8
    (0, "8", "enter"),
    (18, "8", "attempt get"),
    (23, "8", "acquired"),
    (33, "8", "put"),
    (43, "8", "exit"),
    # 9
    (0, "9", "enter"),
    (19, "9", "attempt get"),
    (24, "9", "acquired"),
    (34, "9", "put"),
    (44, "9", "exit"),
}


def test_get_put(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        credits = CreditPool(10)
        for i in range(10):
            create_task(use_get_put(credits, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


def test_async_with(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        credits = CreditPool(10)
        for i in range(10):
            create_task(use_with(credits, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


def test_init_bad_values():
    with pytest.raises(ValueError):
        _ = CreditPool(value=5, capacity=4)

    with pytest.raises(ValueError):
        _ = CreditPool(value=-1)
