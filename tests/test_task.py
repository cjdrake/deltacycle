"""Test deltacycle.Task"""

# pylint: disable=protected-access

import logging
from random import randint

import pytest

from deltacycle import (
    CancelledError,
    Event,
    InvalidStateError,
    Task,
    create_task,
    get_running_loop,
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
        with pytest.raises(InvalidStateError):
            t1.result()
        with pytest.raises(InvalidStateError):
            t1.exception()

        r = await t1

        # Check Result/Exception
        assert r == 42
        assert t1.result() == 42
        assert t1.exception() is None

        # Cannot set a result after task is done
        with pytest.raises(InvalidStateError):
            t1._set_result(42)

    run(main())


def test_one_exception():
    async def cf():
        await sleep(10)
        raise ArithmeticError(42)

    async def main():
        t1 = create_task(cf())

        # Result/Exception not ready yet
        with pytest.raises(InvalidStateError):
            t1.result()
        with pytest.raises(InvalidStateError):
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

        # Cannot set an exception after task is done
        with pytest.raises(InvalidStateError):
            t1._set_exception(ValueError())

    run(main())


EXP1 = {
    # main
    (0, "main enter"),
    (5, "main cancels C1"),
    (5, "main except"),
    (5, "main finally"),
    # C1
    (0, "C1 enter"),
    (5, "C1 except"),
    (5, "C1 finally"),
    # C2
    (0, "C2 enter"),
    (10, "C2 finally"),
    # C3
    (0, "C3 enter"),
    (10, "C3 finally"),
}


def test_cancel_pending(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def cf(name: str, n: int):
        logger.info("%s enter", name)
        try:
            await sleep(n)
        except CancelledError:
            logger.info("%s except", name)
            raise
        finally:
            logger.info("%s finally", name)

    async def main():
        logger.info("main enter")

        t1 = create_task(cf("C1", 1000))
        t2 = create_task(cf("C2", 10))
        t3 = create_task(cf("C3", 10))

        await sleep(5)

        logger.info("main cancels C1")
        t1.cancel()

        try:
            await t1
        except CancelledError:
            logger.info("main except")
        finally:
            logger.info("main finally")

        await t2
        await t3

        assert t1.done()
        assert t1.cancelled()

        # Result should re-raise CancelledError
        with pytest.raises(CancelledError):
            t1.result()
        # So should exception
        with pytest.raises(CancelledError):
            t1.exception()

        # Cannot cancel done task
        with pytest.raises(ValueError):
            t1.cancel()

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


EXP2 = {
    # main
    (0, "main enter"),
    (20, "main exit"),
    # C1
    (0, "C1 enter"),
    (10, "C1 cancelled"),
    (10, "C1 finally"),
    # C2
    (0, "C2 enter"),
    (20, "C2 finally"),
    # C3
    (0, "C3 enter"),
    (20, "C3 finally"),
}


def test_cancel_waiting(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def cf(name: str, event: Event):
        logger.info("%s enter", name)
        try:
            await event.wait()
        except CancelledError:
            logger.info("%s cancelled", name)
        finally:
            logger.info("%s finally", name)

    async def main():
        logger.info("main enter")
        event = Event()
        t1 = create_task(cf("C1", event))
        t2 = create_task(cf("C2", event))
        t3 = create_task(cf("C3", event))

        await sleep(10)

        t1.cancel()

        await sleep(10)

        event.set()

        await t2
        await t3

        logger.info("main exit")

    run(main())
    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2


def test_names():
    async def foo():
        await sleep(10)

    async def bar():
        fiz1 = create_task(fiz(), name="fiz")
        assert fiz1.name == "fiz.0"
        assert fiz1.qualname == "/main/bar.0/fiz.0"
        await sleep(10)

    async def fiz():
        await sleep(10)

    async def main():
        foo1 = create_task(foo())
        foo2 = create_task(foo())
        foo3 = create_task(foo(), name="foo")
        foo4 = create_task(foo(), name="foo")

        loop = get_running_loop()
        assert foo1.parent is loop.main

        assert foo1.name == "0"
        assert foo1.qualname == "/main/0"
        assert foo2.name == "1"
        assert foo2.qualname == "/main/1"
        assert foo3.name == "foo.0"
        assert foo3.qualname == "/main/foo.0"
        assert foo4.name == "foo.1"
        assert foo4.qualname == "/main/foo.1"

        create_task(bar(), name="bar")

    run(main())
