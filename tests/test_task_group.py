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
    # Group 0
    (0, "C0 enter"),
    (5, "C0 exit"),
    # Group 1
    (0, "C1 enter"),
    (10, "C1 exit"),
    # Group 2
    # (0, "C2 enter"),
    # (10, "C2 exit"),
    # Group 3
    (0, "C3 enter"),
    (15, "C3 exit"),
}


def test_group(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("MAIN enter")

        rs = list(range(4))
        async with TaskGroup() as tg:
            t0 = tg.create_task(group_coro("C0", 5, rs[0]))
            t1 = tg.create_task(group_coro("C1", 10, rs[1]))
            # t2 = tg.create_task(group_coro("C2", 10, rs[2]))
            t3 = tg.create_task(group_coro("C3", 15, rs[3]))

        logger.info("MAIN exit")

        assert t0.result() == rs[0]
        assert t1.result() == rs[1]
        # assert t2.result() == rs[2]
        assert t3.result() == rs[3]

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP
