"""Test bugs"""

from typing import Never

import pytest

from deltacycle import TaskGroup, any_of, finish, run, sleep, step

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

    async def drv_clock() -> Never:
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


def test_9():
    async def main():
        await sleep(-1)

    with pytest.raises(ValueError):
        run(main())


def test_10():
    async def main():
        finish()

    r = list(step(main()))
    assert r == [0]


@pytest.mark.xfail(reason="Multiple predicates for same variable is broken")
def test_foo():
    clock = Bool(name="clock")

    async def do_stuff():
        await sleep(10)
        p1 = clock.pred(clock.is_negedge)
        p2 = clock.pred(clock.is_posedge)
        # _WaitQ.push (task, p2) overwrites (task, p1) in _t2p dict
        await any_of(p1, p2)

    async def drv_clock() -> Never:
        clock.next = False
        while True:
            await sleep(5)
            clock.next = not clock.value

    async def main():
        async with TaskGroup() as tg:
            tg.create_task(drv_clock(), name="drv_clock")
            tg.create_task(do_stuff(), name="do_stuff")

    run(main(), until=100)
