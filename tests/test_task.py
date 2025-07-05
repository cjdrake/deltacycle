"""Test deltacycle.Task"""

import logging
from random import randint

import pytest
from pytest import LogCaptureFixture

from deltacycle import (
    Event,
    Interrupt,
    Task,
    TaskState,
    create_task,
    get_current_task,
    irun,
    run,
    sleep,
)

logger = logging.getLogger("deltacycle")


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
    list(irun(main()))


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


def test_interrupt_pending1(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def cf(n: int):
        logger.info("enter")
        try:
            await sleep(n)
        except Interrupt:
            logger.info("except")
            raise
        finally:
            logger.info("finally")

    async def main():
        logger.info("enter")

        t1 = create_task(cf(1000), name="C1")
        t2 = create_task(cf(10), name="C2")
        t3 = create_task(cf(10), name="C3")

        await sleep(5)

        logger.info("interrupts C1")
        t1.interrupt()

        try:
            await t1
        except Interrupt as exc:
            logger.info("except")
            assert t1.exception() is exc
        finally:
            logger.info("finally")

        await t2
        await t3

        assert t1.done()
        assert t1.state() is TaskState.EXCEPTED

        # Result should re-raise Interrupt
        with pytest.raises(Interrupt):
            t1.result()

        # Cannot interrupt done task
        assert not t1.interrupt()

    run(main())
    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


def test_interrupt_pending2(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def cf(n: int):
        logger.info("enter")
        try:
            await sleep(n)
        except Interrupt:
            logger.info("except")
            raise
        finally:
            logger.info("finally")

    async def main():
        logger.info("enter")

        t1 = create_task(cf(1000), name="C1")
        t2 = create_task(cf(10), name="C2")
        t3 = create_task(cf(10), name="C3")

        await sleep(5)

        logger.info("interrupts C1")
        t1.interrupt()

        try:
            await t1
        except Interrupt as exc:
            logger.info("except")
            assert t1.exception() is exc
        finally:
            logger.info("finally")

        await t2
        await t3

        assert t1.done()
        assert t1.state() is TaskState.EXCEPTED

        # Result should re-raise Interrupt
        with pytest.raises(Interrupt):
            t1.result()

        # Cannot interrupt done task
        assert not t1.interrupt()

    list(irun(main()))
    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


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


def test_interrupt_waiting(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def cf(event: Event):
        logger.info("enter")
        try:
            await event
        except Interrupt:
            logger.info("interrupted")
        finally:
            logger.info("finally")

    async def main():
        logger.info("enter")
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

        logger.info("exit")

    run(main())
    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2


EXP3 = {
    (0, "Task started"),
    (1, "Main caught Interrupt from task"),
    (1, "Task interrupting itself"),
}


def test_interrupt_running(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def self_interrupting_task():
        logger.info("Task started")
        await sleep(1)
        task = get_current_task()
        logger.info("Task interrupting itself")
        task.interrupt()  # Interrupt self
        await sleep(1)  # This won't execute
        logger.info("This won't print")

    async def main():
        task = create_task(self_interrupting_task())
        try:
            await task
        except Interrupt:
            logger.info("Main caught Interrupt from task")

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP3


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
