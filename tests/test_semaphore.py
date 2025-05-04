"""Test deltacycle.Semaphore"""

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
    # 0
    (0, "0 enter"),
    (10, "0 attempt acquire"),
    (10, "0 acquired"),
    (20, "0 release"),
    (30, "0 exit"),
    # 1
    (0, "1 enter"),
    (11, "1 attempt acquire"),
    (11, "1 acquired"),
    (21, "1 release"),
    # 2
    (0, "2 enter"),
    (12, "2 attempt acquire"),
    (12, "2 acquired"),
    (22, "2 release"),
    (32, "2 exit"),
    # 3
    (0, "3 enter"),
    (13, "3 attempt acquire"),
    (13, "3 acquired"),
    (23, "3 release"),
    (33, "3 exit"),
    # 4
    (0, "4 enter"),
    (14, "4 attempt acquire"),
    (20, "4 acquired"),
    (30, "4 release"),
    (40, "4 exit"),
    # 5
    (0, "5 enter"),
    (15, "5 attempt acquire"),
    (21, "5 acquired"),
    (31, "5 release"),
    (41, "5 exit"),
    # 6
    (0, "6 enter"),
    (16, "6 attempt acquire"),
    (22, "6 acquired"),
    (32, "6 release"),
    (42, "6 exit"),
    # 7
    (0, "7 enter"),
    (17, "7 attempt acquire"),
    (23, "7 acquired"),
    (31, "1 exit"),
    (33, "7 release"),
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


def test_bounded():
    async def use_unbounded():
        sem = Semaphore(2)

        await sem.acquire()
        await sem.acquire()
        sem.release()
        sem.release()

        # No exception!
        sem.release()
        assert sem.cnt() == 3  # pylint: disable = protected-access

    run(use_unbounded())


def test_unbounded():
    async def use_bounded():
        sem = BoundedSemaphore(2)
        assert sem.maxcnt == 2

        await sem.acquire()
        await sem.acquire()
        sem.release()
        sem.release()

        # Exception!
        with pytest.raises(ValueError):
            sem.release()

    run(use_bounded())


def test_init_bad_values():
    with pytest.raises(ValueError):
        _ = Semaphore(0)

    with pytest.raises(ValueError):
        _ = Semaphore(-1)
