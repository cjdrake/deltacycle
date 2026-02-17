"""Test deltacycle.Task"""

from random import randint

import pytest

from deltacycle import (
    AllOf,
    AnyOf,
    Event,
    Interrupt,
    Task,
    all_of,
    any_of,
    create_task,
    get_current_task,
    now,
    run,
    sleep,
    step,
)

from .conftest import trace


def test_results():
    async def cf1(x0: int, x1: int) -> int:
        await sleep(randint(1, 5))
        return x0 * x1

    async def cf2(t0: Task, t1: Task) -> int:
        await t0
        await t1
        await sleep(randint(1, 5))
        return t0.result() * t1.result()

    async def main():
        t1 = create_task(cf1(2, 3))
        t2 = create_task(cf1(5, 7))
        t5 = create_task(cf2(t1, t2))

        t3 = create_task(cf1(11, 13))
        t4 = create_task(cf1(17, 19))
        t6 = create_task(cf2(t3, t4))

        t7 = create_task(c7 := cf2(t5, t6))

        assert t7.coro is c7

        r = await t7
        assert r == 2 * 3 * 5 * 7 * 11 * 13 * 17 * 19

    run(main())


def test_one_result():
    async def cf() -> int:
        await sleep(10)
        return 42

    async def main():
        t1 = create_task(cf())

        # Result/Exception not ready yet
        with pytest.raises(RuntimeError):
            t1.result()
        with pytest.raises(RuntimeError):
            t1.exception()

        r = await t1

        # Check Result/Exception
        assert r == 42
        assert t1.result() == 42
        assert t1.exception() is None

    run(main())


def test_one_exception():
    async def cf():
        await sleep(10)
        raise ArithmeticError(42)

    async def main():
        t1 = create_task(cf())

        # Result/Exception not ready yet
        with pytest.raises(RuntimeError):
            t1.result()
        with pytest.raises(RuntimeError):
            t1.exception()

        try:
            _ = await t1
        except ArithmeticError as e:
            # Check Result/Exception
            assert e.args[0] == 42
            try:
                _ = t1.result()
            except ArithmeticError as ee:
                assert ee is e
            assert t1.exception() is e
        else:
            assert False

    run(main())
    list(step(main()))


EXP1 = {
    # main
    (0, "main", "enter"),
    (5, "main", "interrupts C1"),
    (5, "main", "except"),
    (5, "main", "finally"),
    # C1
    (0, "C1", "enter"),
    (5, "C1", "except"),
    (5, "C1", "finally"),
    # C2
    (0, "C2", "enter"),
    (10, "C2", "finally"),
    # C3
    (0, "C3", "enter"),
    (10, "C3", "finally"),
}


def test_interrupt_pending1(captrace: set[tuple[int, str, str]]):
    async def cf(n: int):
        trace("enter")
        try:
            await sleep(n)
        except Interrupt:
            trace("except")
            raise
        finally:
            trace("finally")

    async def main():
        trace("enter")

        t1 = create_task(cf(1000), name="C1")
        t2 = create_task(cf(10), name="C2")
        t3 = create_task(cf(10), name="C3")

        await sleep(5)

        trace("interrupts C1")
        t1.interrupt()

        try:
            await t1
        except Interrupt as exc:
            trace("except")
            assert t1.exception() is exc
        finally:
            trace("finally")

        await t2
        await t3

        assert t1.done()
        assert t1.state() is Task.State.EXCEPTED

        # Result should re-raise Interrupt
        with pytest.raises(Interrupt):
            t1.result()

        # Cannot interrupt done task
        assert not t1.interrupt()

    run(main())
    assert captrace == EXP1


def test_interrupt_pending2(captrace: set[tuple[int, str, str]]):
    async def cf(n: int):
        trace("enter")
        try:
            await sleep(n)
        except Interrupt:
            trace("except")
            raise
        finally:
            trace("finally")

    async def main():
        trace("enter")

        t1 = create_task(cf(1000), name="C1")
        t2 = create_task(cf(10), name="C2")
        t3 = create_task(cf(10), name="C3")

        await sleep(5)

        trace("interrupts C1")
        t1.interrupt()

        try:
            await t1
        except Interrupt as exc:
            trace("except")
            assert t1.exception() is exc
        finally:
            trace("finally")

        await t2
        await t3

        assert t1.done()
        assert t1.state() is Task.State.EXCEPTED

        # Result should re-raise Interrupt
        with pytest.raises(Interrupt):
            t1.result()

        # Cannot interrupt done task
        assert not t1.interrupt()

    list(step(main()))
    assert captrace == EXP1


EXP2 = {
    # main
    (0, "main", "enter"),
    (20, "main", "exit"),
    # C1
    (0, "C1", "enter"),
    (10, "C1", "interrupted"),
    (10, "C1", "finally"),
    # C2
    (0, "C2", "enter"),
    (20, "C2", "finally"),
    # C3
    (0, "C3", "enter"),
    (20, "C3", "finally"),
}


def test_interrupt_waiting(captrace: set[tuple[int, str, str]]):
    async def cf(event: Event):
        trace("enter")
        try:
            await event
        except Interrupt:
            trace("interrupted")
        finally:
            trace("finally")

    async def main():
        trace("enter")
        event = Event()
        t1 = create_task(cf(event), name="C1")
        t2 = create_task(cf(event), name="C2")
        t3 = create_task(cf(event), name="C3")

        await sleep(10)

        t1.interrupt()

        await sleep(10)

        event.set()

        await t2
        await t3

        trace("exit")

    run(main())
    assert captrace == EXP2


EXP3 = {
    (0, "T1", "started"),
    (1, "main", "caught interrupt from task"),
    (1, "T1", "interrupting itself"),
}


def test_interrupt_running(captrace: set[tuple[int, str, str]]):
    async def self_interrupting_task():
        trace("started")
        await sleep(1)
        task = get_current_task()
        trace("interrupting itself")
        task.interrupt()  # Interrupt self
        await sleep(1)  # This won't execute
        trace("This won't print")

    async def main():
        task = create_task(self_interrupting_task(), name="T1")
        try:
            await task
        except Interrupt:
            trace("caught interrupt from task")

    run(main())
    assert captrace == EXP3


def test_names():
    async def foo():
        await sleep(10)

    async def bar():
        fiz1 = create_task(fiz(), name="fiz")
        assert fiz1.name == "fiz"
        await sleep(10)

    async def fiz():
        await sleep(10)

    async def main():
        foo1 = create_task(foo())
        foo2 = create_task(foo())
        foo3 = create_task(foo(), name="foo")
        foo4 = create_task(foo(), name="foo")

        assert foo1.name.startswith("Task-")
        assert foo2.name.startswith("Task-")
        assert foo3.name == "foo"
        assert foo4.name == "foo"

        create_task(bar(), name="bar")

    run(main())


def test_task_any1():
    async def cf(t: int):
        await sleep(t)

    async def main():
        t1 = create_task(cf(5), name="T1")
        t2 = create_task(cf(10), name="T2")
        t3 = create_task(cf(15), name="T3")

        t = await any_of(t1, t2, t3)
        assert t is t1
        assert now() == 5

    run(main())


def test_task_any2():
    async def main():
        y = await AnyOf()
        assert y is None
        assert now() == 0

    run(main())


def test_task_all1():
    async def cf(t: int):
        await sleep(t)

    async def main():
        t1 = create_task(cf(5), name="T1")
        t2 = create_task(cf(10), name="T2")
        t3 = create_task(cf(15), name="T3")

        ts = await all_of(t1, t2, t3)
        assert ts == (t1, t2, t3)
        assert now() == 15

    run(main())


def test_task_all2():
    async def cf(t: int):
        await sleep(t)

    async def main():
        t1 = create_task(cf(5), name="T1")
        t2 = create_task(cf(10), name="T2")
        t3 = create_task(cf(15), name="T3")

        await sleep(6)  # t1 is done

        ts = await AllOf(t1, t2, t3)
        assert ts == (t1, t2, t3)
        assert now() == 15

    run(main())


def test_task_all3():
    async def cf(t: int):
        await sleep(t)

    async def main():
        t1 = create_task(cf(5), name="T1")
        t2 = create_task(cf(10), name="T2")
        t3 = create_task(cf(15), name="T3")

        await sleep(20)  # all are done

        ts = await all_of(t1, t2, t3)
        assert ts == (t1, t2, t3)
        assert now() == 20

    run(main())


def test_task_all4():
    async def cf(t: int):
        await sleep(t)

    async def main():
        t1 = create_task(cf(5), name="T1")
        t2 = create_task(cf(10), name="T2")
        t3 = create_task(cf(15), name="T3")

        ts = await AllOf(t1, t2, t3)
        assert ts == (t1, t2, t3)
        assert now() == 15

    run(main())
