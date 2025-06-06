"""Test deltacycle.Event"""

import logging

from pytest import LogCaptureFixture

from deltacycle import Event, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def primary(event: Event):
    logger.info("enter")

    await sleep(10)

    # T=10
    logger.info("set")
    event.set()
    assert event

    await sleep(10)

    # T=20
    logger.info("clear")
    event.clear()
    assert not event

    await sleep(10)

    # T=30
    logger.info("set")
    event.set()
    assert event

    logger.info("exit")


async def secondary(event: Event):
    logger.info("enter")

    # Event clear
    logger.info("waiting")
    await event

    # Event set @10
    logger.info("running")
    await sleep(10)

    # Event clear
    logger.info("waiting")
    await event

    # Event set @30
    logger.info("running")
    await sleep(10)

    # Event still set: return immediately
    await event

    logger.info("exit")


EXP1 = {
    # P
    (0, "P", "enter"),
    (10, "P", "set"),
    (20, "P", "clear"),
    (30, "P", "set"),
    (30, "P", "exit"),
    # S1
    (0, "S1", "enter"),
    (0, "S1", "waiting"),
    (10, "S1", "running"),
    (20, "S1", "waiting"),
    (30, "S1", "running"),
    (40, "S1", "exit"),
    # S2
    (0, "S2", "enter"),
    (0, "S2", "waiting"),
    (10, "S2", "running"),
    (20, "S2", "waiting"),
    (30, "S2", "running"),
    (40, "S2", "exit"),
    # S3
    (0, "S3", "enter"),
    (0, "S3", "waiting"),
    (10, "S3", "running"),
    (20, "S3", "waiting"),
    (30, "S3", "running"),
    (40, "S3", "exit"),
}


def test_acquire_release(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        event = Event()
        create_task(primary(event), name="P")
        create_task(secondary(event), name="S1")
        create_task(secondary(event), name="S2")
        create_task(secondary(event), name="S3")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1
