"""Simulate a register file."""

# pyright: reportAttributeAccessIssue=false

import logging

from pytest import LogCaptureFixture

from deltacycle import AnyOf, create_task, run, sleep

from .common import Bool, Int, IntMem

logger = logging.getLogger("deltacycle")


# wr_en, wr_addr, wr_data, rd_addr, rd_data
VALS = [
    (True, 0, 42, 0, 0),
    (True, 1, 43, 0, 42),
    (True, 2, 44, 1, 43),
    (True, 3, 45, 2, 44),
    (True, 4, 46, 3, 45),
    (True, 5, 47, 4, 46),
    (True, 6, 48, 5, 47),
    (True, 7, 49, 6, 48),
    (True, 8, 50, 7, 49),
    (True, 9, 51, 8, 50),
    # Note: Same WrData
    (True, 0, 42, 9, 51),
    (False, 0, 0, 0, 42),
]


def test_regfile(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    clk = Bool(name="clk")
    period = 10

    wr_en = Bool(name="wr_en")
    wr_addr = Int(name="wr_addr")
    wr_data = Int(name="wr_data")

    rd_addr = Int(name="rd_addr")
    rd_data = Int(name="rd_data")

    # State
    regs = IntMem(name="regs")

    async def drv_clk():
        clk.next = False
        while True:
            await sleep(period // 2)
            clk.next = not clk.prev

    async def drv_inputs():
        for we, wa, wd, ra, _ in VALS:
            wr_en.next = we
            wr_addr.next = wa
            wr_data.next = wd
            rd_addr.next = ra
            await clk.posedge()

    async def mon_outputs():
        while True:
            await clk.posedge()
            logger.info(
                "wr_en=%d wr_addr=%d wr_data=%d rd_addr=%d rd_data=%d",
                wr_en.prev,
                wr_addr.prev,
                wr_data.prev,
                rd_addr.prev,
                rd_data.prev,
            )

    async def wr_port():
        def clk_pred():
            return clk.is_posedge() and wr_en.prev

        while True:
            await clk.pred(clk_pred)
            regs[wr_addr.prev].next = wr_data.prev

    async def rd_port():
        while True:
            await AnyOf(regs, rd_addr)
            rd_data.next = regs.value[rd_addr.value]

    async def main():
        create_task(drv_clk(), priority=2, name="drv_clk")
        create_task(drv_inputs(), priority=2, name="drv_inputs")
        create_task(mon_outputs(), priority=3, name="mon_outputs")
        create_task(wr_port(), priority=2, name="wr_port")
        create_task(rd_port(), priority=1, name="rd_port")

    run(main(), until=120)

    # Check log messages
    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == [
        (period * i + 5, f"wr_en={we:d} wr_addr={wa} wr_data={wd} rd_addr={ra} rd_data={rd}")
        for i, (we, wa, wd, ra, rd) in enumerate(VALS)
    ]

    for i in range(10):
        assert regs[i].prev == 42 + i
