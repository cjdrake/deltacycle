"""Simulate a 4-bit adder."""

# pylint: disable=logging-fstring-interpolation

import logging

from deltacycle import Singular, create_task, model_wait, run, sleep

logger = logging.getLogger("deltacycle")


class Bool(Singular):
    """Variable that supports dumping to memory."""

    def __init__(self):
        super().__init__(value=False)

    def is_posedge(self) -> bool:
        return not self._prev and self._next

    def is_negedge(self) -> bool:
        return self._prev and not self._next

    async def posedge(self):
        await model_wait((self, self.is_posedge))

    async def negedge(self):
        await model_wait((self, self.is_negedge))


def test_add(caplog):
    """Test 4-bit adder simulation."""
    caplog.set_level(logging.INFO, logger="deltacycle")

    # Inputs
    clk = Bool()
    a = Bool()
    b = Bool()
    ci = Bool()

    # Outputs
    s = Bool()
    co = Bool()

    async def p_clk():
        while True:
            await sleep(5)
            clk.next = not clk.prev

    async def p_a_b_ci():
        await model_wait((clk, clk.is_posedge))
        a.next = False
        b.next = True

        await model_wait((clk, clk.is_posedge))
        a.next = True
        b.next = False

        await model_wait((clk, clk.is_posedge))
        a.next = True
        b.next = True

    async def p_s_co():
        while True:
            await model_wait((a, None), (b, None), (ci, None))
            s.next = a.value ^ b.value ^ ci.value
            co.next = a.value & b.value | (a.value | b.value) & ci.value
            logger.info(f"s={s.value:d}, co={co.value:d}")

    async def main():
        create_task(p_clk(), region=2)
        create_task(p_a_b_ci(), region=2)
        create_task(p_s_co(), region=1)

    run(main(), until=30)

    # Check log messages
    msgs = {(r.time, r.msg) for r in caplog.records}
    assert msgs == {
        (5, "s=1, co=0"),
        (15, "s=1, co=0"),
        (25, "s=0, co=1"),
    }
