"""Test deltacycle.Semaphore"""

# pyright: reportAttributeAccessIssue=false

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import (
    AllOf,
    BoundedSemaphore,
    Lock,
    Semaphore,
    all_of,
    create_task,
    now,
    run,
    sleep,
)

logger = logging.getLogger("deltacycle")


async def use_acquire_release(sem: Semaphore, t1: int, t2: int):
    logger.info("enter")

    await sleep(t1)

    logger.info("attempt get")
    await sem.get()
    logger.info("acquired")

    try:
        await sleep(t2)
    finally:
        logger.info("put")
        sem.put()

    await sleep(10)
    logger.info("exit")


async def use_with(sem: Semaphore, t1: int, t2: int):
    logger.info("enter")

    await sleep(t1)

    logger.info("attempt get")
    async with sem.req():
        logger.info("acquired")
        await sleep(t2)
    logger.info("put")

    await sleep(10)
    logger.info("exit")


EXP = {
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
    (20, "4", "acquired"),
    (30, "4", "put"),
    (40, "4", "exit"),
    # 5
    (0, "5", "enter"),
    (15, "5", "attempt get"),
    (21, "5", "acquired"),
    (31, "5", "put"),
    (41, "5", "exit"),
    # 6
    (0, "6", "enter"),
    (16, "6", "attempt get"),
    (22, "6", "acquired"),
    (32, "6", "put"),
    (42, "6", "exit"),
    # 7
    (0, "7", "enter"),
    (17, "7", "attempt get"),
    (23, "7", "acquired"),
    (31, "1", "exit"),
    (33, "7", "put"),
    (43, "7", "exit"),
}


def test_acquire_release(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        sem = Semaphore(4)
        for i in range(8):
            create_task(use_acquire_release(sem, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_async_with(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        sem = Semaphore(4)
        for i in range(8):
            create_task(use_with(sem, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
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


def test_priority():
    async def request(lock: Lock, p: int):
        await sleep(5)
        await lock.get(priority=p)
        await sleep(5)
        lock.put()

    async def main():
        lock = Lock()
        t3 = create_task(request(lock, 3), name="T3")
        t2 = create_task(request(lock, 2), name="T2")
        t1 = create_task(request(lock, 1), name="T1")
        t0 = create_task(request(lock, 0), name="T0", priority=-1)

        ts = await all_of(t3, t2, t1, t0)
        assert ts == (t0, t1, t2, t3)
        assert now() == 25

    run(main())


def test_init_bad_values():
    with pytest.raises(ValueError):
        _ = Semaphore(0)

    with pytest.raises(ValueError):
        _ = Semaphore(-1)


def test_schedule_all1():
    async def cf(s: Semaphore, t1: int, t2: int, t3: int):
        await sleep(t1)
        await s.get()
        await sleep(t2)
        s.put()
        await sleep(t3)

    async def main():
        lock = Lock()
        t1 = create_task(cf(lock, 0, 10, 10))

        await sleep(1)
        await AllOf(t1, lock.req())

        assert now() == 20
        assert lock._cnt == 0
        lock.put()

    run(main())


def test_schedule_all2():
    async def cf(s: Semaphore, t1: int, t2: int, t3: int):
        await sleep(t1)
        await s.get()
        await sleep(t2)
        s.put()
        await sleep(t3)

    async def main():
        lock = Lock()
        t1 = create_task(cf(lock, 0, 10, 10))

        await sleep(1)
        sks = await all_of(t1, lock.req())

        assert sks == (lock, t1)
        assert now() == 20
        assert lock._cnt == 0
        lock.put()

    run(main())
