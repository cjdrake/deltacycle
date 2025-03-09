"""Test seqlogic.sim.Lock class."""

import logging

import pytest

from deltacycle import CancelledError, Task, TaskGroup, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def basic_c1():
    logger.info("C1 enter")

    await sleep(10)
    logger.info("C1")
    await sleep(10)
    logger.info("C1")
    await sleep(10)
    logger.info("C1")
    await sleep(10)

    logger.info("C1 exit")


async def basic_c2(t: Task):
    logger.info("C2 enter")

    logger.info("C2 suspend")
    await t
    logger.info("C2 resume")

    await t
    await sleep(10)
    await t

    logger.info("C2 exit")


EXP1 = {
    (0, "C1 enter"),
    (0, "C2 enter"),
    (0, "C2 suspend"),
    (10, "C1"),
    (20, "C1"),
    (30, "C1"),
    (40, "C1 exit"),
    (40, "C2 resume"),
    (50, "C2 exit"),
}


def test_basic(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        t1 = create_task(basic_c1())
        create_task(basic_c2(t1))

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


async def cancel_c1():
    logger.info("C1 enter")

    try:
        await sleep(1000)
    except CancelledError:
        logger.info("C1 except")
        raise
    finally:
        logger.info("C1 finally")


async def cancel_c2():
    logger.info("C2 enter")

    task = create_task(cancel_c1())

    await sleep(1)

    logger.info("C2 cancels C1")
    task.cancel()

    try:
        await task
    except CancelledError:
        logger.info("C2 except")
    finally:
        logger.info("C2 finally")

    assert task.done()
    assert task.cancelled()

    # Result should re-raise CancelledError
    with pytest.raises(CancelledError):
        task.result()
    # So should exception
    with pytest.raises(CancelledError):
        task.exception()


EXP2 = {
    (0, "C2 enter"),
    (0, "C1 enter"),
    (1, "C2 cancels C1"),
    (1, "C1 except"),
    (1, "C1 finally"),
    (1, "C2 except"),
    (1, "C2 finally"),
}


def test_cancel(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    run(cancel_c2())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2


async def group_c1():
    logger.info("C1 enter")
    await sleep(5)
    logger.info("C1 exit")
    return 1


async def group_c2():
    logger.info("C2 enter")
    await sleep(10)
    logger.info("C2 exit")
    return 2


async def group_c3():
    logger.info("C3 enter")
    await sleep(15)
    logger.info("C3 exit")
    return 3


EXP3 = {
    (0, "C1 enter"),
    (0, "C2 enter"),
    (0, "C3 enter"),
    (5, "C1 exit"),
    (10, "C2 exit"),
    (15, "C3 exit"),
    (15, "MAIN"),
}


def test_group(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        async with TaskGroup() as tg:
            t1 = tg.create_task(group_c1())
            t2 = tg.create_task(group_c2())
            t3 = tg.create_task(group_c3())

        logger.info("MAIN")

        assert t1.result() == 1
        assert t2.result() == 2
        assert t3.result() == 3

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP3
