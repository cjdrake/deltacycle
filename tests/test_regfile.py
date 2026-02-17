"""Simulate a register file."""

from deltacycle import any_of, create_task, run, sleep

from .common import Bool, Int, IntMem
from .conftest import trace

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

EXP = {
    (
        10 * i + 5,
        "mon_outputs",
        f"wr_en={VALS[i][0]:b} wr_addr={VALS[i][1]:x} wr_data={VALS[i][2]:02x} "
        f"rd_addr={VALS[i][3]:x} rd_data={VALS[i][4]:02x}",
    )
    for i, _ in enumerate(VALS)
}


def test_regfile(captrace: set[tuple[int, str, str]]):
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
            trace(
                f"wr_en={wr_en.prev:b} wr_addr={wr_addr.prev:x} wr_data={wr_data.prev:02x} "
                f"rd_addr={rd_addr.prev:x} rd_data={rd_data.prev:02x}"
            )

    async def wr_port():
        def clk_pred():
            return clk.is_posedge() and wr_en.prev

        while True:
            await clk.pred(clk_pred)
            regs[wr_addr.prev].next = wr_data.prev

    async def rd_port():
        while True:
            await any_of(regs, rd_addr)
            rd_data.next = regs.value[rd_addr.value]

    async def main():
        create_task(drv_clk(), name="drv_clk", priority=2)
        create_task(drv_inputs(), name="drv_inputs", priority=2)
        create_task(mon_outputs(), name="mon_outputs", priority=3)
        create_task(wr_port(), name="wr_port", priority=2)
        create_task(rd_port(), name="rd_port", priority=1)

    run(main(), until=120)

    for i in range(10):
        assert regs[i].prev == 42 + i

    assert captrace == EXP
