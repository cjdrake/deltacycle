"""Test seqlogic.sim.Lock class."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

import logging

from pytest import LogCaptureFixture

from deltacycle import Lock, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def use_acquire_release(lock: Lock, t1: int, t2: int):
    logger.info("enter")

    await sleep(t1)

    logger.info("attempt get")
    await lock.get()
    logger.info("acquired")

    try:
        await sleep(t2)
    finally:
        logger.info("put")
        lock.put()

    await sleep(10)
    logger.info("exit")


async def use_with(lock: Lock, t1: int, t2: int):
    logger.info("enter")

    await sleep(t1)

    logger.info("attempt get")
    async with lock.req():
        logger.info("acquired")
        await sleep(t2)
    logger.info("put")

    await sleep(10)
    logger.info("exit")


EXP = {
    (0, "0", "enter"),
    (0, "1", "enter"),
    (0, "2", "enter"),
    (0, "3", "enter"),
    (10, "0", "attempt get"),
    (10, "0", "acquired"),
    (11, "1", "attempt get"),
    (12, "2", "attempt get"),
    (13, "3", "attempt get"),
    (20, "0", "put"),
    (20, "1", "acquired"),
    (30, "0", "exit"),
    (30, "1", "put"),
    (30, "2", "acquired"),
    (40, "1", "exit"),
    (40, "2", "put"),
    (40, "3", "acquired"),
    (50, "2", "exit"),
    (50, "3", "put"),
    (60, "3", "exit"),
}


def test_acquire_release(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        lock = Lock()
        for i in range(4):
            create_task(use_acquire_release(lock, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_async_with(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        lock = Lock()
        for i in range(4):
            create_task(use_with(lock, i + 10, 10), name=f"{i}")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP
