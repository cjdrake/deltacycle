"""Test seqlogic.sim finish."""

import logging

from deltacycle import LoopState, create_task, finish, get_running_loop, run, sleep

logger = logging.getLogger("deltacycle")


async def ctl():
    logger.info("CTL enter")
    await sleep(100)

    # Force all PING threads to stop immediately
    logger.info("CTL finish")
    finish()


async def ping(name: str, period: int):
    logger.info("%s enter", name)
    while True:
        await sleep(period)
        logger.info("%s PING", name)


EXP1 = {
    (0, "CTL enter"),
    (0, "FOO enter"),
    (0, "BAR enter"),
    (0, "FIZ enter"),
    (0, "BUZ enter"),
    (3, "FOO PING"),
    (5, "BAR PING"),
    (6, "FOO PING"),
    (7, "FIZ PING"),
    (9, "FOO PING"),
    (10, "BAR PING"),
    (11, "BUZ PING"),
    (12, "FOO PING"),
    (14, "FIZ PING"),
    (15, "BAR PING"),
    (15, "FOO PING"),
    (18, "FOO PING"),
    (20, "BAR PING"),
    (21, "FIZ PING"),
    (21, "FOO PING"),
    (22, "BUZ PING"),
    (24, "FOO PING"),
    (25, "BAR PING"),
    (27, "FOO PING"),
    (28, "FIZ PING"),
    (30, "BAR PING"),
    (30, "FOO PING"),
    (33, "BUZ PING"),
    (33, "FOO PING"),
    (35, "FIZ PING"),
    (35, "BAR PING"),
    (36, "FOO PING"),
    (39, "FOO PING"),
    (40, "BAR PING"),
    (42, "FIZ PING"),
    (42, "FOO PING"),
    (44, "BUZ PING"),
    (45, "BAR PING"),
    (45, "FOO PING"),
    (48, "FOO PING"),
    (49, "FIZ PING"),
    (50, "BAR PING"),
    (51, "FOO PING"),
    (54, "FOO PING"),
    (55, "BUZ PING"),
    (55, "BAR PING"),
    (56, "FIZ PING"),
    (57, "FOO PING"),
    (60, "BAR PING"),
    (60, "FOO PING"),
    (63, "FIZ PING"),
    (63, "FOO PING"),
    (65, "BAR PING"),
    (66, "BUZ PING"),
    (66, "FOO PING"),
    (69, "FOO PING"),
    (70, "FIZ PING"),
    (70, "BAR PING"),
    (72, "FOO PING"),
    (75, "BAR PING"),
    (75, "FOO PING"),
    (77, "BUZ PING"),
    (77, "FIZ PING"),
    (78, "FOO PING"),
    (80, "BAR PING"),
    (81, "FOO PING"),
    (84, "FIZ PING"),
    (84, "FOO PING"),
    (85, "BAR PING"),
    (87, "FOO PING"),
    (88, "BUZ PING"),
    (90, "BAR PING"),
    (90, "FOO PING"),
    (91, "FIZ PING"),
    (93, "FOO PING"),
    (95, "BAR PING"),
    (96, "FOO PING"),
    (98, "FIZ PING"),
    (99, "BUZ PING"),
    (99, "FOO PING"),
    (100, "CTL finish"),
}


def test_finish(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        create_task(ctl())
        create_task(ping("FOO", 3))
        create_task(ping("BAR", 5))
        create_task(ping("FIZ", 7))
        create_task(ping("BUZ", 11))

    # Subsequent calls to run() have no effect
    run(main())

    loop = get_running_loop()
    assert loop.state() is LoopState.FINISHED

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1
