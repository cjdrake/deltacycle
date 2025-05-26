"""Test deltacycle._loop.finish"""

import logging

from pytest import LogCaptureFixture

from deltacycle import LoopState, create_task, finish, get_loop, irun, run, sleep

logger = logging.getLogger("deltacycle")


async def ctl():
    logger.info("enter")
    await sleep(100)

    # Force all PING threads to stop immediately
    logger.info("finish")
    finish()


async def ping(period: int):
    logger.info("enter")
    while True:
        await sleep(period)
        logger.info("PING")


EXP1 = {
    # CTL
    (0, "CTL", "enter"),
    (100, "CTL", "finish"),
    # FOO
    (0, "FOO", "enter"),
    (3, "FOO", "PING"),
    (6, "FOO", "PING"),
    (9, "FOO", "PING"),
    (12, "FOO", "PING"),
    (15, "FOO", "PING"),
    (18, "FOO", "PING"),
    (21, "FOO", "PING"),
    (24, "FOO", "PING"),
    (27, "FOO", "PING"),
    (30, "FOO", "PING"),
    (33, "FOO", "PING"),
    (36, "FOO", "PING"),
    (39, "FOO", "PING"),
    (42, "FOO", "PING"),
    (45, "FOO", "PING"),
    (48, "FOO", "PING"),
    (51, "FOO", "PING"),
    (54, "FOO", "PING"),
    (57, "FOO", "PING"),
    (60, "FOO", "PING"),
    (63, "FOO", "PING"),
    (66, "FOO", "PING"),
    (69, "FOO", "PING"),
    (72, "FOO", "PING"),
    (75, "FOO", "PING"),
    (78, "FOO", "PING"),
    (81, "FOO", "PING"),
    (84, "FOO", "PING"),
    (87, "FOO", "PING"),
    (90, "FOO", "PING"),
    (93, "FOO", "PING"),
    (96, "FOO", "PING"),
    (99, "FOO", "PING"),
    # BAR
    (0, "BAR", "enter"),
    (5, "BAR", "PING"),
    (10, "BAR", "PING"),
    (15, "BAR", "PING"),
    (20, "BAR", "PING"),
    (25, "BAR", "PING"),
    (30, "BAR", "PING"),
    (35, "BAR", "PING"),
    (40, "BAR", "PING"),
    (45, "BAR", "PING"),
    (50, "BAR", "PING"),
    (55, "BAR", "PING"),
    (60, "BAR", "PING"),
    (65, "BAR", "PING"),
    (70, "BAR", "PING"),
    (75, "BAR", "PING"),
    (80, "BAR", "PING"),
    (85, "BAR", "PING"),
    (90, "BAR", "PING"),
    (95, "BAR", "PING"),
    # FIZ
    (0, "FIZ", "enter"),
    (7, "FIZ", "PING"),
    (14, "FIZ", "PING"),
    (21, "FIZ", "PING"),
    (28, "FIZ", "PING"),
    (35, "FIZ", "PING"),
    (42, "FIZ", "PING"),
    (49, "FIZ", "PING"),
    (56, "FIZ", "PING"),
    (63, "FIZ", "PING"),
    (70, "FIZ", "PING"),
    (77, "FIZ", "PING"),
    (84, "FIZ", "PING"),
    (91, "FIZ", "PING"),
    (98, "FIZ", "PING"),
    # BUZ
    (0, "BUZ", "enter"),
    (11, "BUZ", "PING"),
    (22, "BUZ", "PING"),
    (33, "BUZ", "PING"),
    (44, "BUZ", "PING"),
    (55, "BUZ", "PING"),
    (66, "BUZ", "PING"),
    (77, "BUZ", "PING"),
    (88, "BUZ", "PING"),
    (99, "BUZ", "PING"),
}


def test_finish1(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        create_task(ctl(), name="CTL")
        create_task(ping(3), name="FOO")
        create_task(ping(5), name="BAR")
        create_task(ping(7), name="FIZ")
        create_task(ping(11), name="BUZ")

    # Subsequent calls to run() have no effect
    run(main())

    loop = get_loop()
    assert loop is not None
    assert loop.state() is LoopState.FINISHED

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


def test_finish2(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        create_task(ctl(), name="CTL")
        create_task(ping(3), name="FOO")
        create_task(ping(5), name="BAR")
        create_task(ping(7), name="FIZ")
        create_task(ping(11), name="BUZ")

    # Subsequent calls to run() have no effect
    list(irun(main()))

    loop = get_loop()
    assert loop is not None
    assert loop.state() is LoopState.FINISHED
    assert loop.done()
    assert loop.finished()

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1
