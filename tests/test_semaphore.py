"""Test seqlogic.sim.Semaphore class."""

import logging

import pytest

from deltacycle import BoundedSemaphore, Semaphore, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def use_acquire_release(sem: Semaphore, name: str, t1: int, t2: int):
    logger.info("%s enter", name)

    await sleep(t1)

    logger.info("%s attempt acquire", name)
    await sem.acquire()
    logger.info("%s acquired", name)

    try:
        await sleep(t2)
    finally:
        logger.info("%s release", name)
        sem.release()

    await sleep(10)
    logger.info("%s exit", name)


async def use_with(sem: Semaphore, name: str, t1: int, t2: int):
    logger.info("%s enter", name)

    await sleep(t1)

    logger.info("%s attempt acquire", name)
    async with sem:
        logger.info("%s acquired", name)
        await sleep(t2)
    logger.info("%s release", name)

    await sleep(10)
    logger.info("%s exit", name)


EXP = {
    (0, "0 enter"),
    (0, "1 enter"),
    (0, "2 enter"),
    (0, "3 enter"),
    (0, "4 enter"),
    (0, "5 enter"),
    (0, "6 enter"),
    (0, "7 enter"),
    (10, "0 attempt acquire"),
    (10, "0 acquired"),
    (11, "1 attempt acquire"),
    (11, "1 acquired"),
    (12, "2 attempt acquire"),
    (12, "2 acquired"),
    (13, "3 attempt acquire"),
    (13, "3 acquired"),
    (14, "4 attempt acquire"),
    (15, "5 attempt acquire"),
    (16, "6 attempt acquire"),
    (17, "7 attempt acquire"),
    (20, "0 release"),
    (20, "4 acquired"),
    (21, "1 release"),
    (21, "5 acquired"),
    (22, "2 release"),
    (22, "6 acquired"),
    (23, "3 release"),
    (23, "7 acquired"),
    (30, "0 exit"),
    (30, "4 release"),
    (31, "1 exit"),
    (31, "5 release"),
    (32, "2 exit"),
    (32, "6 release"),
    (33, "3 exit"),
    (33, "7 release"),
    (40, "4 exit"),
    (41, "5 exit"),
    (42, "6 exit"),
    (43, "7 exit"),
}


def test_acquire_release(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        sem = Semaphore(4)
        for i in range(8):
            create_task(use_acquire_release(sem, f"{i}", i + 10, 10))

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_async_with(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        sem = Semaphore(4)
        for i in range(8):
            create_task(use_with(sem, f"{i}", i + 10, 10))

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_bounds():
    async def use_unbounded():
        sem = Semaphore(2)

        await sem.acquire()
        await sem.acquire()
        sem.release()
        sem.release()

        # No exception!
        sem.release()
        assert sem._cnt == 3  # pylint: disable = protected-access

    async def use_bounded():
        sem = BoundedSemaphore(2)

        await sem.acquire()
        await sem.acquire()
        sem.release()
        sem.release()

        # Exception!
        sem.release()

    run(use_unbounded())

    with pytest.raises(ValueError):
        run(use_bounded())
