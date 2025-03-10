"""Test seqlogic.sim.wait function."""

import logging

import pytest

from deltacycle import create_task, run, sleep, wait

logger = logging.getLogger("deltacycle")


async def c(i: int, t: int):
    logger.info("C%d enter", i)
    await sleep(t)
    logger.info("C%d exit", i)


EXP1 = {
    (0, "MAIN enter"),
    (0, "C1 enter"),
    (0, "C2 enter"),
    (0, "C3 enter"),
    (5, "C1 exit"),
    (5, "MAIN wait done"),
    (10, "C2 exit"),
    (15, "C3 exit"),
    (15, "MAIN exit"),
}


def test_first(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("MAIN enter")

        t1 = create_task(c(1, 5))
        t2 = create_task(c(2, 10))
        t3 = create_task(c(3, 15))

        done, pend = await wait([t1, t2, t3], return_when="FIRST_COMPLETED")
        assert done == {t1}
        assert pend == {t2, t3}

        logger.info("MAIN wait done")

        await t2
        await t3

        logger.info("MAIN exit")

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


EXP2 = {
    (0, "MAIN enter"),
    (0, "C1 enter"),
    (0, "C2 enter"),
    (0, "C3 enter"),
    (5, "C1 exit"),
    (10, "C2 exit"),
    (15, "C3 exit"),
    (15, "MAIN exit"),
}


def test_all(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("MAIN enter")

        t1 = create_task(c(1, 5))
        t2 = create_task(c(2, 10))
        t3 = create_task(c(3, 15))

        done, pend = await wait([t1, t2, t3], return_when="ALL_COMPLETED")
        assert done == {t1, t2, t3}
        assert not pend

        logger.info("MAIN exit")

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2


def test_error1():
    async def main():
        await wait([], return_when="invalid")

    with pytest.raises(ValueError):
        run(main())


def test_error2():
    async def main():
        await wait([], return_when="FIRST_EXCEPTION")

    with pytest.raises(NotImplementedError):
        run(main())
