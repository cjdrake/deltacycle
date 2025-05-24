"""Test deltacycle.Semaphore"""

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import BoundedSemaphore, Semaphore, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def use_acquire_release(sem: Semaphore, name: str, t1: int, t2: int):
    logger.info("%s enter", name)

    await sleep(t1)

    logger.info("%s attempt get", name)
    await sem.get()
    logger.info("%s acquired", name)

    try:
        await sleep(t2)
    finally:
        logger.info("%s put", name)
        sem.put()

    await sleep(10)
    logger.info("%s exit", name)


async def use_with(sem: Semaphore, name: str, t1: int, t2: int):
    logger.info("%s enter", name)

    await sleep(t1)

    logger.info("%s attempt get", name)
    async with sem:
        logger.info("%s acquired", name)
        await sleep(t2)
    logger.info("%s put", name)

    await sleep(10)
    logger.info("%s exit", name)


EXP = {
    # 0
    (0, "0 enter"),
    (10, "0 attempt get"),
    (10, "0 acquired"),
    (20, "0 put"),
    (30, "0 exit"),
    # 1
    (0, "1 enter"),
    (11, "1 attempt get"),
    (11, "1 acquired"),
    (21, "1 put"),
    # 2
    (0, "2 enter"),
    (12, "2 attempt get"),
    (12, "2 acquired"),
    (22, "2 put"),
    (32, "2 exit"),
    # 3
    (0, "3 enter"),
    (13, "3 attempt get"),
    (13, "3 acquired"),
    (23, "3 put"),
    (33, "3 exit"),
    # 4
    (0, "4 enter"),
    (14, "4 attempt get"),
    (20, "4 acquired"),
    (30, "4 put"),
    (40, "4 exit"),
    # 5
    (0, "5 enter"),
    (15, "5 attempt get"),
    (21, "5 acquired"),
    (31, "5 put"),
    (41, "5 exit"),
    # 6
    (0, "6 enter"),
    (16, "6 attempt get"),
    (22, "6 acquired"),
    (32, "6 put"),
    (42, "6 exit"),
    # 7
    (0, "7 enter"),
    (17, "7 attempt get"),
    (23, "7 acquired"),
    (31, "1 exit"),
    (33, "7 put"),
    (43, "7 exit"),
}


def test_acquire_release(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        sem = Semaphore(4)
        for i in range(8):
            create_task(use_acquire_release(sem, f"{i}", i + 10, 10))

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_async_with(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        sem = Semaphore(4)
        for i in range(8):
            create_task(use_with(sem, f"{i}", i + 10, 10))

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_unbounded():
    async def use_unbounded():
        sem = Semaphore(2)

        await sem.get()
        await sem.get()
        sem.put()
        sem.put()

        # No exception!
        sem.put()

    run(use_unbounded())


def test_bounded():
    async def use_bounded():
        sem = BoundedSemaphore(2)

        await sem.get()
        await sem.get()

        sem.put()
        sem.put()

        # Exception!
        with pytest.raises(ValueError):
            sem.put()

    async def main():
        create_task(use_bounded())

    run(main())


def test_init_bad_values():
    with pytest.raises(ValueError):
        _ = Semaphore(0)

    with pytest.raises(ValueError):
        _ = Semaphore(-1)
