"""Test bugs"""

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import TaskGroup, run, sleep

from .common import Bool

logger = logging.getLogger("deltacycle")


@pytest.mark.xfail
def test_2(caplog: LogCaptureFixture):
    clock = Bool()

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
