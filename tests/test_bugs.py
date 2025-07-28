"""Test bugs"""

# pyright: reportAttributeAccessIssue=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

import logging

from pytest import LogCaptureFixture

from deltacycle import TaskGroup, run, sleep

from .common import Bool

logger = logging.getLogger("deltacycle")


EXP2 = {
    (5, "do_stuff", "first"),
    (15, "do_stuff", "second"),
    (25, "do_stuff", "third"),
    (35, "do_stuff", "fourth"),
}


def test_2(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    clock = Bool(name="clock")

    async def do_stuff():
        await clock.posedge()
        logger.info("first")
        await clock.posedge()
        logger.info("second")
        await clock.posedge()
        logger.info("third")
        await clock.posedge()
        logger.info("fourth")

    async def drv_clock():
        clock.next = False
        while True:
            await sleep(5)
            clock.next = not clock.value

    async def main():
        async with TaskGroup() as tg:
            tg.create_task(drv_clock(), name="drv_clock")
            tg.create_task(do_stuff(), name="do_stuff")

    run(main(), until=100)

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2
