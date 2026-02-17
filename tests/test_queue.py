"""Test deltacycle.queue"""

from deltacycle import Queue, create_task, run, sleep

from .conftest import trace

EXP1 = {
    (0, "P", "0"),
    (0, "C", "0"),
    (10, "P", "1"),
    (10, "C", "1"),
    (20, "P", "2"),
    (20, "C", "2"),
    (30, "P", "3"),
    (30, "C", "3"),
    (40, "P", "4"),
    (40, "C", "4"),
    (50, "P", "5"),
    (50, "C", "5"),
    (60, "P", "6"),
    (60, "C", "6"),
    (70, "P", "7"),
    (70, "C", "7"),
    (80, "P", "8"),
    (80, "C", "8"),
    (90, "P", "9"),
    (90, "C", "9"),
    (100, "P", "CLOSED"),
}


def test_prod_cons1(captrace: set[tuple[int, str, str]]):
    q: Queue[int] = Queue()

    async def prod():
        for i in range(10):
            trace(f"{i}")
            await q.put(i)
            await sleep(10)
        trace("CLOSED")

    async def cons():
        while True:
            i = await q.get()
            trace(f"{i}")

    async def main():
        create_task(prod(), name="P")
        create_task(cons(), name="C")

    run(main())

    assert captrace == EXP1


EXP2 = {
    (0, "P", "0"),
    (0, "P", "1"),
    (0, "P", "2"),
    (10, "C", "0"),
    (10, "P", "3"),
    (20, "C", "1"),
    (20, "P", "4"),
    (30, "C", "2"),
    (30, "P", "5"),
    (40, "C", "3"),
    (40, "P", "6"),
    (50, "C", "4"),
    (50, "P", "7"),
    (60, "C", "5"),
    (60, "P", "8"),
    (70, "C", "6"),
    (70, "P", "9"),
    (80, "C", "7"),
    (80, "P", "CLOSED"),
    (90, "C", "8"),
    (100, "C", "9"),
}


def test_prod_cons2(captrace: set[tuple[int, str, str]]):
    q: Queue[int] = Queue(2)

    assert q.capacity == 2

    async def prod():
        for i in range(10):
            trace(f"{i}")
            await q.put(i)
        trace("CLOSED")

    async def cons():
        while True:
            await sleep(10)
            i = await q.get()
            trace(f"{i}")

    async def main():
        create_task(prod(), name="P")
        create_task(cons(), name="C")

    run(main())

    assert captrace == EXP2


def test_prod_cons3():
    q: Queue[int] = Queue(2)
    assert len(q) == 0

    async def prod():
        assert q.try_put(1)
        assert len(q) == 1

        assert q.try_put(2)
        assert len(q) == 2

        assert not q.try_put(3)

    async def cons():
        await sleep(10)

        success, value = q.try_get()
        assert success
        assert value == 1

        success, value = q.try_get()
        assert success
        assert value == 2

        success, value = q.try_get()
        assert not success

    async def main():
        create_task(prod())
        create_task(cons())

    run(main())
