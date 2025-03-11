"""Simulate a register file."""

import logging

from deltacycle import changed, create_task, resume, run, sleep

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


def test_regfile(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    clk = Bool()
    period = 10

    wr_en = Bool()
    wr_addr = Int()
    wr_data = Int()

    rd_addr = Int()
    rd_data = Int()

    # State
    regs = IntMem()

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
            await resume((clk, clk_pred))
            regs[wr_addr.prev].next = wr_data.prev

    async def rd_port():
        while True:
            await changed(regs, rd_addr)
            rd_data.next = regs.value[rd_addr.value]

    async def main():
        create_task(drv_clk(), region=2)
        create_task(drv_inputs(), region=2)
        create_task(mon_outputs(), region=3)
        create_task(wr_port(), region=2)
        create_task(rd_port(), region=1)

    run(main(), until=120)

    # Check log messages
    msgs = [(r.time, r.getMessage()) for r in caplog.records]
    assert msgs == [
        (period * i + 5, f"wr_en={we:d} wr_addr={wa} wr_data={wd} rd_addr={ra} rd_data={rd}")
        for i, (we, wa, wd, ra, rd) in enumerate(VALS)
    ]

    for i in range(10):
        assert regs[i].prev == 42 + i
