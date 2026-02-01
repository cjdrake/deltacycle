"""Test bugs"""

from pytest import CaptureFixture

from deltacycle import TaskGroup, run, sleep

from .common import Bool, ttprint

EXP2 = """\
[   5][do_stuff] first
[  15][do_stuff] second
[  25][do_stuff] third
[  35][do_stuff] fourth
"""


def test_2(capsys: CaptureFixture[str]):
    clock = Bool(name="clock")

    async def do_stuff():
        await clock.posedge()
        ttprint("first")
        await clock.posedge()
        ttprint("second")
        await clock.posedge()
        ttprint("third")
        await clock.posedge()
        ttprint("fourth")

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

    cap = capsys.readouterr()
    # msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    # assert msgs == EXP2
    assert cap.out == EXP2
