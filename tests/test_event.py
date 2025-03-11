"""Test seqlogic.sim.Event class."""

import logging

from deltacycle import Event, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def primary(event: Event, name: str):
    logger.info("%s enter", name)

    await sleep(10)

    # T=10
    logger.info("%s set", name)
    event.set()
    assert event.is_set()

    await sleep(10)

    # T=20
    logger.info("%s clear", name)
    event.clear()
    assert not event.is_set()

    await sleep(10)

    # T=30
    logger.info("%s set", name)
    event.set()
    assert event.is_set()

    logger.info("%s exit", name)


async def secondary(event: Event, name: str):
    logger.info("%s enter", name)

    # Event clear
    logger.info("%s waiting", name)
    await event.wait()

    # Event set @10
    logger.info("%s running", name)
    await sleep(10)

    # Event clear
    logger.info("%s waiting", name)
    await event.wait()

    # Event set @30
    logger.info("%s running", name)
    await sleep(10)

    # Event still set: return immediately
    await event.wait()

    logger.info("%s exit", name)


EXP1 = {
    # P1
    (0, "P1 enter"),
    (10, "P1 set"),
    (20, "P1 clear"),
    (30, "P1 set"),
    (30, "P1 exit"),
    # S1
    (0, "S1 enter"),
    (0, "S1 waiting"),
    (10, "S1 running"),
    (20, "S1 waiting"),
    (30, "S1 running"),
    (40, "S1 exit"),
    # S2
    (0, "S2 enter"),
    (0, "S2 waiting"),
    (10, "S2 running"),
    (20, "S2 waiting"),
    (30, "S2 running"),
    (40, "S2 exit"),
    # S3
    (0, "S3 enter"),
    (0, "S3 waiting"),
    (10, "S3 running"),
    (20, "S3 waiting"),
    (30, "S3 running"),
    (40, "S3 exit"),
}


def test_acquire_release(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        event = Event()
        create_task(primary(event, "P1"))
        create_task(secondary(event, "S1"))
        create_task(secondary(event, "S2"))
        create_task(secondary(event, "S3"))

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1
