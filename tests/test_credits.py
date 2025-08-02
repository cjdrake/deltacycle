"""Test deltacycle.CreditPool"""

# pyright: reportAttributeAccessIssue=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import AllOf, CreditPool, TaskGroup, all_of, create_task, now, run, sleep

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
        credits.put(n=2)

    await sleep(10)
    logger.info("exit")


async def use_try_get_put(credits: CreditPool, t1: int, t2: int):
    logger.info("enter")

    await sleep(t1)

    logger.info("attempt get")
    while not credits.try_get(n=2):
        await sleep(1)
    logger.info("acquired")

    try:
        await sleep(t2)
    finally:
        logger.info("put")
        credits.put(n=2)

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

EXP2 = {
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
    # NOTE: Ordering mismatch starts here.
    (24, "5", "acquired"),
    (34, "5", "put"),
    # NOTE: But total time (44) remains the same
    (44, "5", "exit"),
    # 6
    (0, "6", "enter"),
    (16, "6", "attempt get"),
    (23, "6", "acquired"),
    (33, "6", "put"),
    (43, "6", "exit"),
    # 7
    (0, "7", "enter"),
    (17, "7", "attempt get"),
    (22, "7", "acquired"),
    (32, "7", "put"),
    (42, "7", "exit"),
    # 8
    (0, "8", "enter"),
    (18, "8", "attempt get"),
    (21, "8", "acquired"),
    (31, "8", "put"),
    (41, "8", "exit"),
    # 9
    (0, "9", "enter"),
    (19, "9", "attempt get"),
    (20, "9", "acquired"),
    (30, "9", "put"),
    (40, "9", "exit"),
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


def test_try_get_put(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        credits = CreditPool(10)
        for i in range(10):
            create_task(use_try_get_put(credits, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2


def test_async_with(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        credits = CreditPool(10)
        for i in range(10):
            create_task(use_with(credits, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


def test_bounded():
    async def use_bounded():
        credits = CreditPool(value=5, capacity=5)

        await credits.get(n=2)
        await credits.get(n=3)

        credits.put(n=2)
        credits.put(n=3)

        # Exception!
        with pytest.raises(OverflowError):
            credits.put(n=1)

    async def main():
        create_task(use_bounded())

    run(main())


def test_priority():
    async def request(credits: CreditPool, p: int):
        await sleep(5)
        await credits.get(n=2, priority=p)
        await sleep(5)
        credits.put()

    async def main():
        credits = CreditPool(value=2, capacity=2)
        t3 = create_task(request(credits, 3), name="T3")
        t2 = create_task(request(credits, 2), name="T2")
        t1 = create_task(request(credits, 1), name="T1")
        t0 = create_task(request(credits, 0), name="T0", priority=-1)

        ts = await all_of(t3, t2, t1, t0)
        assert ts == (t0, t1, t2, t3)
        assert now() == 25

    run(main())


def test_init_bad_values():
    with pytest.raises(ValueError):
        _ = CreditPool(value=5, capacity=4)

    with pytest.raises(ValueError):
        _ = CreditPool(value=-1)


def test_schedule_all1():
    async def cf(credits: CreditPool, t1: int, t2: int, t3: int):
        await sleep(t1)
        await credits.get(n=10)
        await sleep(t2)
        credits.put(n=10)
        await sleep(t3)

    async def main():
        credits = CreditPool(value=10, capacity=10)
        t1 = create_task(cf(credits, 0, 10, 10))

        await sleep(1)
        ys = await AllOf(t1, credits.req(n=10))

        assert ys == (credits, t1)
        assert now() == 20
        assert not credits
        credits.put(n=2)

    run(main())


def test_schedule_all2():
    async def cf(credits: CreditPool, t1: int, t2: int, t3: int):
        await sleep(t1)
        await credits.get(n=10)
        await sleep(t2)
        credits.put(n=10)
        await sleep(t3)

    async def main():
        credits = CreditPool(value=10, capacity=10)
        t1 = create_task(cf(credits, 0, 10, 10))

        await sleep(1)
        ys = await all_of(t1, credits.req(n=10))

        assert ys == (credits, t1)
        assert now() == 20
        assert not credits
        credits.put(n=10)

    run(main())


def test_overflow1():
    async def a(credits: CreditPool):
        credits.put(5)
        await sleep(5)

        # b gets 10
        await sleep(5)

        credits.put(7)  # 5 + 7 - 10 should NOT overflow

    async def b(credits: CreditPool):
        # a puts 5
        await sleep(5)

        await credits.get(10)
        await sleep(5)

    async def main():
        credits = CreditPool(capacity=10)
        async with TaskGroup() as tg:
            tg.create_task(a(credits))
            tg.create_task(b(credits))

    run(main())
