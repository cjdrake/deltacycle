"""Test bugs"""

from typing import Never

import pytest

from deltacycle import Queue, TaskGroup, any_of, finish, run, sleep, step

from .common import Bool
from .conftest import trace

EXP_2 = {
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

    assert captrace == EXP_2


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


EXP_11 = {
    # Use both pos/neg edge triggers
    (5, "do_np_edge", ""),
    (10, "do_np_edge", ""),
    (15, "do_np_edge", ""),
    (20, "do_np_edge", ""),
    # Use edge trigger
    (5, "do_edge", ""),
    (10, "do_edge", ""),
    (15, "do_edge", ""),
    (20, "do_edge", ""),
}


def test_11(captrace: set[tuple[int, str, str]]):
    clock = Bool(name="clock")

    async def do_np_edge():
        while True:
            p1 = clock.pred(clock.is_negedge)
            p2 = clock.pred(clock.is_posedge)
            p3 = clock.pred(clock.is_negedge)  # redundant
            p4 = clock.pred(clock.is_posedge)  # redundant
            await any_of(p1, p2, p3, p4)
            trace()

    async def do_edge():
        while True:
            await clock.edge()
            trace()

    async def drv_clock() -> Never:
        clock.next = False
        while True:
            await sleep(5)
            clock.next = not clock.value

    async def main():
        async with TaskGroup() as tg:
            tg.create_task(drv_clock(), name="drv_clock")
            tg.create_task(do_np_edge(), name="do_np_edge")
            tg.create_task(do_edge(), name="do_edge")

    run(main(), until=25)

    assert captrace == EXP_11


@pytest.mark.xfail(reason="Queue wakeup is not atomic")
def test_12():
    q: Queue[int] = Queue(capacity=1)

    # Producer
    async def p():
        await sleep(5)

        assert q.try_put(42)
        # Consumer thread scheduled w/ priority=1

        # Steal the reservation: IndexError???
        await q.get(priority=-1)

    # Consumer
    async def c():
        # Blocks for 5 (until producer does try_put)
        await q.get(priority=1)

    async def main():
        async with TaskGroup() as tg:
            tg.create_task(p(), name="producer")
            tg.create_task(c(), name="consumer")

    run(main())
