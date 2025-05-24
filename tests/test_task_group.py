"""Test deltacycle.TaskGroup"""

import logging

from pytest import LogCaptureFixture

from deltacycle import TaskGroup, run, sleep

logger = logging.getLogger("deltacycle")


async def group_coro(name: str, t: int, r: int):
    logger.info("%s enter", name)
    await sleep(t)
    logger.info("%s exit", name)
    return r


EXP = {
    # Main
    (0, "MAIN enter"),
    (15, "MAIN exit"),
    # Group 1
    (0, "C1 enter"),
    (5, "C1 exit"),
    # Group 2
    (0, "C2 enter"),
    (10, "C2 exit"),
    # Group 3
    (0, "C3 enter"),
    (15, "C3 exit"),
}


def test_group(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("MAIN enter")

        r1, r2, r3 = 1, 2, 3
        async with TaskGroup() as tg:
            t1 = tg.create_task(group_coro("C1", 5, r1))
            t2 = tg.create_task(group_coro("C2", 10, r2))
            t3 = tg.create_task(group_coro("C3", 15, r3))

        logger.info("MAIN exit")

        assert t1.result() == r1
        assert t2.result() == r2
        assert t3.result() == r3

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP
