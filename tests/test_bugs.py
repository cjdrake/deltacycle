"""Test bugs"""

from deltacycle import TaskGroup, run, sleep

from .common import Bool
from .conftest import trace

EXP2 = {
    (5, "do_stuff", "first"),
    (15, "do_stuff", "second"),
    (25, "do_stuff", "third"),
    (35, "do_stuff", "fourth"),
}


def test_2(captrace: set[tuple[int, str, str]]):
    clock = Bool(name="clock")

    async def do_stuff():
        await clock.posedge()
        trace("first")
        await clock.posedge()
        trace("second")
        await clock.posedge()
        trace("third")
        await clock.posedge()
        trace("fourth")

    async def drv_clock():
        clock.next = False
        while True:
            await sleep(5)
            clock.next = not clock.value

    async def main():
        async with TaskGroup() as tg:
            tg.create_task(drv_clock(), name="drv_clock")
            tg.create_task(do_stuff(), name="do_stuff")

    run(main(), until=100)

    assert captrace == EXP2
