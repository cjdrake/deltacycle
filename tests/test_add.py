"""Simulate a 4-bit adder."""

import logging

from pytest import LogCaptureFixture

from deltacycle import changed, create_task, run, sleep

from .common import Bool

logger = logging.getLogger("deltacycle")


# a, b, ci, s, co
VALS = [
    (False, False, False, False, False),
    (False, False, True, True, False),
    (False, True, False, True, False),
    (False, True, True, False, True),
    (True, False, False, True, False),
    (True, False, True, False, True),
    (True, True, False, False, True),
    (True, True, True, True, True),
]


def test_add(caplog: LogCaptureFixture):
    """Test 4-bit adder simulation."""
    caplog.set_level(logging.INFO, logger="deltacycle")

    period = 10

    # Inputs
    clk = Bool(name="clk")

    a = Bool(name="a")
    b = Bool(name="b")
    ci = Bool(name="ci")

    # Outputs
    s = Bool(name="s")
    co = Bool(name="co")

    async def drv_clk():
        clk.next = False
        while True:
            await sleep(period // 2)
            clk.next = not clk.prev

    async def drv_inputs():
        for a_val, b_val, ci_val, _, _ in VALS:
            a.next = a_val
            b.next = b_val
            ci.next = ci_val
            await clk.posedge()

    async def drv_outputs():
        while True:
            await changed(a, b, ci)
            g = a.value & b.value
            p = a.value | b.value
            s.next = a.value ^ b.value ^ ci.value
            co.next = g | p & ci.value

    async def mon_outputs():
        while True:
            await clk.posedge()
            logger.info("s=%d co=%d", s.prev, co.prev)

    async def main():
        create_task(drv_clk(), priority=0, name="drv_clk")
        create_task(drv_inputs(), priority=0, name="drv_inputs")
        create_task(drv_outputs(), priority=-1, name="drv_outputs")
        create_task(mon_outputs(), priority=1, name="mon_outputs")

    until = period * len(VALS)
    run(main(), until=until)

    # Check log messages
    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == [
        (period * i + 5, f"s={s_val:d} co={co_val:d}")
        for i, (_, _, _, s_val, co_val) in enumerate(VALS)
    ]
