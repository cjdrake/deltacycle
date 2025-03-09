"""Test seqlogic.sim.Lock class."""

import logging

from deltacycle import Lock, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def use_acquire_release(lock: Lock, name: str, t1: int, t2: int):
    logger.info("%s enter", name)

    await sleep(t1)

    logger.info("%s attempt acquire", name)
    await lock.acquire()
    logger.info("%s acquired", name)

    try:
        await sleep(t2)
    finally:
        logger.info("%s release", name)
        lock.release()

    await sleep(10)
    logger.info("%s exit", name)


async def use_with(lock: Lock, name: str, t1: int, t2: int):
    logger.info("%s enter", name)

    await sleep(t1)

    logger.info("%s attempt acquire", name)
    async with lock:
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
    (10, "0 attempt acquire"),
    (10, "0 acquired"),
    (11, "1 attempt acquire"),
    (12, "2 attempt acquire"),
    (13, "3 attempt acquire"),
    (20, "0 release"),
    (20, "1 acquired"),
    (30, "0 exit"),
    (30, "1 release"),
    (30, "2 acquired"),
    (40, "1 exit"),
    (40, "2 release"),
    (40, "3 acquired"),
    (50, "2 exit"),
    (50, "3 release"),
    (60, "3 exit"),
}


def test_acquire_release(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        lock = Lock()
        for i in range(4):
            create_task(use_acquire_release(lock, f"{i}", i + 10, 10))

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_async_with(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        lock = Lock()
        for i in range(4):
            create_task(use_with(lock, f"{i}", i + 10, 10))

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP
