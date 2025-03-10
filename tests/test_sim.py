"""Test seqlogic.sim module."""

import logging

from deltacycle import create_task, get_running_loop, irun, run, sleep

from .common import Bool

logger = logging.getLogger("deltacycle")


async def drv_clk(clk: Bool):
    while True:
        await sleep(5)
        clk.next = not clk.prev


async def drv_a(a: Bool, clk: Bool):
    while True:
        await clk.edge()
        a.next = not a.prev


async def drv_b(b: Bool, clk: Bool):
    i = 0
    while True:
        await clk.edge()
        if i % 2 == 0:
            b.next = not b.prev
        else:
            b.next = b.prev
        i += 1


async def drv_c(c: Bool, clk: Bool):
    i = 0
    while True:
        await clk.edge()
        if i % 3 == 0:
            c.next = not c.prev
        i += 1


async def mon(a: Bool, b: Bool, c: Bool, clk: Bool):
    while True:
        await clk.edge()
        logger.info("a=%d b=%d c=%d", a.prev, b.prev, c.prev)


EXP = {
    (5, "a=0 b=0 c=0"),
    (10, "a=1 b=1 c=1"),
    (15, "a=0 b=1 c=1"),
    (20, "a=1 b=0 c=1"),
    (25, "a=0 b=0 c=0"),
    (30, "a=1 b=1 c=0"),
    (35, "a=0 b=1 c=0"),
    (40, "a=1 b=0 c=1"),
    (45, "a=0 b=0 c=1"),
}


def test_vars_run(caplog):
    """Test generic variable functionality."""
    caplog.set_level(logging.INFO, logger="deltacycle")

    clk = Bool()
    a = Bool()
    b = Bool()
    c = Bool()

    async def main():
        create_task(drv_clk(clk), region=2)
        create_task(drv_a(a, clk), region=2)
        create_task(drv_b(b, clk), region=2)
        create_task(drv_c(c, clk), region=2)
        create_task(mon(a, b, c, clk), region=3)

    # Relative run limit
    run(main(), ticks=25)

    # Absolute run limit
    run(loop=get_running_loop(), until=50)

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP


def test_vars_iter(caplog):
    """Test generic variable functionality."""
    caplog.set_level(logging.INFO, logger="deltacycle")

    clk = Bool()
    a = Bool()
    b = Bool()
    c = Bool()

    async def main():
        create_task(drv_clk(clk), region=2)
        create_task(drv_a(a, clk), region=2)
        create_task(drv_b(b, clk), region=2)
        create_task(drv_c(c, clk), region=2)
        create_task(mon(a, b, c, clk), region=3)

    for _ in irun(main(), until=25):
        pass

    for _ in irun(loop=get_running_loop(), until=50):
        pass

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP
