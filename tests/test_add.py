"""Simulate a 4-bit adder."""

from pytest import CaptureFixture

from deltacycle import any_of, create_task, run, sleep

from .common import Bool, tprint

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

EXP = "".join(f"[{10 * i + 5:4}] s={VALS[i][3]:b} co={VALS[i][4]:b}\n" for i, _ in enumerate(VALS))


def test_add(capsys: CaptureFixture[str]):
    """Test 4-bit adder simulation."""
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
            await any_of(a, b, ci)
            g = a.value & b.value
            p = a.value | b.value
            s.next = a.value ^ b.value ^ ci.value
            co.next = g | p & ci.value

    async def mon_outputs():
        while True:
            await clk.posedge()
            tprint(f"s={s.prev:b}", f"co={co.prev:b}")

    async def main():
        create_task(drv_clk(), priority=0, name="drv_clk")
        create_task(drv_inputs(), priority=0, name="drv_inputs")
        create_task(drv_outputs(), priority=-1, name="drv_outputs")
        create_task(mon_outputs(), priority=1, name="mon_outputs")

    until = period * len(VALS)
    run(main(), until=until)

    cap = capsys.readouterr()
    assert cap.out == EXP
