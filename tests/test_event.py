"""Test seqlogic.sim.Event class."""

import logging

from deltacycle import Event, create_task, run, sleep

logger = logging.getLogger("deltacycle")


async def primary(event: Event, name: str):
    logger.info("%s enter", name)
    await sleep(10)
    logger.info("%s set", name)
    event.set()
    assert event.is_set()
    await sleep(10)
    logger.info("%s exit", name)


async def secondary(event: Event, name: str):
    logger.info("%s enter", name)
    logger.info("%s waiting", name)
    await event.wait()
    logger.info("%s running", name)
    await sleep(10)
    logger.info("%s exit", name)


EXP1 = {
    (0, "P1 enter"),
    (0, "S1 enter"),
    (0, "S1 waiting"),
    (0, "S2 enter"),
    (0, "S2 waiting"),
    (0, "S3 enter"),
    (0, "S3 waiting"),
    (10, "P1 set"),
    (10, "S1 running"),
    (10, "S2 running"),
    (10, "S3 running"),
    (20, "P1 exit"),
    (20, "S1 exit"),
    (20, "S2 exit"),
    (20, "S3 exit"),
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
