"""Test deltacycle.TaskGroup"""

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import Task, TaskGroup, TaskState, get_current_task_group, run, sleep

logger = logging.getLogger("deltacycle")


async def cf_r(t: int, r: int):
    logger.info("enter")
    await sleep(t)
    logger.info("exit")
    return r


async def cf_x(t: int, r: int):
    logger.info("enter")
    await sleep(t)
    raise ArithmeticError(r)


async def cf_c(name: str, t0: int, r0: int, t1: int, r1: int):
    tg = get_current_task_group()
    assert tg is not None
    logger.info("enter")
    await sleep(t0)
    tg.create_task(cf_r(t1, r1), name=name)
    logger.info("exit")
    return r0


EXP1 = {
    # Main
    (0, "main", "enter"),
    (15, "main", "exit"),
    # Coro 0
    (0, "C0", "enter"),
    (5, "C0", "exit"),
    # Coro 1
    (0, "C1", "enter"),
    (10, "C1", "exit"),
    # Coro 2
    (0, "C2", "enter"),
    (10, "C2", "exit"),
    # Coro 3
    (0, "C3", "enter"),
    (15, "C3", "exit"),
}


def test_group(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("enter")

        ts: list[Task] = []
        async with TaskGroup() as tg:
            ts.append(tg.create_task(cf_r(5, 0), name="C0"))
            ts.append(tg.create_task(cf_r(10, 1), name="C1"))
            ts.append(tg.create_task(cf_r(10, 2), name="C2"))
            ts.append(tg.create_task(cf_r(15, 3), name="C3"))

        logger.info("exit")

        assert ts[0].result() == 0
        assert ts[1].result() == 1
        assert ts[2].result() == 2
        assert ts[3].result() == 3

    run(main())
    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


EXP2 = {
    # Main
    (0, "main", "enter"),
    (10, "main", "exit"),
    # Weirdo
    (0, "X0", "enter"),
    # Coro 0 - completes
    (0, "C0", "enter"),
    (5, "C0", "exit"),
    # Coro 1 - completes
    (0, "C1", "enter"),
    (10, "C1", "exit"),
    # Coro 2 - raises exception
    (0, "C2", "enter"),
    # Coro 3 - raises exception
    (0, "C3", "enter"),
    # Coro 4 - completes
    (0, "C4", "enter"),
    (10, "C4", "exit"),
    # Coro 5,6,7 - cancelled
    (0, "C5", "enter"),
    (0, "C6", "enter"),
    (0, "C7", "enter"),
}


def test_group_child_except(caplog: LogCaptureFixture):
    """One child raises an exception, others are cancelled."""
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("enter")

        ts: list[Task] = []
        with pytest.raises(ExceptionGroup) as e:
            async with TaskGroup() as tg:
                # Handle weird case of done child
                await tg.create_task(sleep(0))

                # Another weird case of done child that raised an exception
                try:
                    await tg.create_task(cf_x(0, 69), name="X0")
                except ArithmeticError:
                    pass

                # These tasks will complete successfully
                ts.append(tg.create_task(cf_r(5, 0), name="C0"))
                ts.append(tg.create_task(cf_r(10, 1), name="C1"))
                # These tasks will raise an exception
                ts.append(tg.create_task(cf_x(10, 2), name="C2"))
                ts.append(tg.create_task(cf_x(10, 3), name="C3"))
                # This task will also complete successfully
                # (It completes before cancellation takes effect)
                ts.append(tg.create_task(cf_r(10, 4), name="C4"))
                # These tasks will be cancelled
                ts.append(tg.create_task(cf_r(11, 5), name="C5"))
                ts.append(tg.create_task(cf_r(13, 6), name="C6"))
                ts.append(tg.create_task(cf_r(15, 7), name="C7"))

        assert ts[0].result() == 0
        assert ts[1].result() == 1
        assert ts[4].result() == 4

        assert ts[5].state() is TaskState.CANCELLED
        assert ts[6].state() is TaskState.CANCELLED
        assert ts[7].state() is TaskState.CANCELLED

        exc = ts[2].exception()
        assert isinstance(exc, ArithmeticError) and exc.args == (2,)
        exc = ts[3].exception()
        assert isinstance(exc, ArithmeticError) and exc.args == (3,)

        excs = e.value.args[1]
        assert [type(exc) for exc in excs] == [ArithmeticError, ArithmeticError]
        assert [exc.args for exc in excs] == [(2,), (3,)]

        logger.info("exit")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2


EXP3 = {
    (0, "main", "enter"),
    (0, "main", "exit"),
}


def test_group_except(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("enter")

        ts: list[Task] = []
        with pytest.raises(ArithmeticError) as e:
            async with TaskGroup() as tg:
                # Handle weird case of done child
                await tg.create_task(sleep(0))

                ts.append(tg.create_task(cf_r(5, 0), name="C0"))
                ts.append(tg.create_task(cf_r(10, 1), name="C1"))

                raise ArithmeticError(42)

        assert ts[0].state() is TaskState.CANCELLED
        assert ts[1].state() is TaskState.CANCELLED
        assert e.value.args == (42,)

        logger.info("exit")

    run(main())
    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP3


EXP4 = {
    # Main
    (0, "main", "enter"),
    (10, "main", "exit"),
    # Coros 0,1,2,3
    (0, "C0", "enter"),
    (2, "C0", "exit"),
    (0, "C1", "enter"),
    (2, "C1", "exit"),
    (0, "C2", "enter"),
    (2, "C2", "exit"),
    (0, "C3", "enter"),
    (2, "C3", "exit"),
    # Newborns 0,1 - completes
    (2, "N0", "enter"),
    (9, "N0", "exit"),
    (2, "N1", "enter"),
    (10, "N1", "exit"),
    # Newborn 2 - cancelled
    (2, "N2", "enter"),
    (2, "N3", "enter"),
    # Coro 4,5 - completes
    (0, "C4", "enter"),
    (5, "C4", "exit"),
    (0, "C5", "enter"),
    (10, "C5", "exit"),
    # Coro 6,7 - raises exception
    (0, "C6", "enter"),
    (0, "C7", "enter"),
    # Coro 8 - completes
    (10, "C8", "exit"),
    (0, "C8", "enter"),
    # Coros 9,10 - cancelled
    (0, "C9", "enter"),
    (0, "C10", "enter"),
}


def test_group_newborns_except(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        logger.info("enter")

        ts: list[Task] = []
        with pytest.raises(ExceptionGroup) as e:
            async with TaskGroup() as tg:
                # Newborns
                ts.append(tg.create_task(cf_c("N0", 2, 0, 7, 10), name="C0"))
                ts.append(tg.create_task(cf_c("N1", 2, 1, 8, 11), name="C1"))
                ts.append(tg.create_task(cf_c("N2", 2, 2, 9, 12), name="C2"))
                ts.append(tg.create_task(cf_c("N3", 2, 3, 10, 13), name="C3"))

                # These tasks will complete successfully
                ts.append(tg.create_task(cf_r(5, 4), name="C4"))
                ts.append(tg.create_task(cf_r(10, 5), name="C5"))
                # These tasks will raise an exception
                ts.append(tg.create_task(cf_x(10, 6), name="C6"))
                ts.append(tg.create_task(cf_x(10, 7), name="C7"))
                # This task will also complete successfully
                # (It completes before cancellation takes effect)
                ts.append(tg.create_task(cf_r(10, 8), name="C8"))
                # These tasks will be cancelled
                ts.append(tg.create_task(cf_r(11, 9), name="C9"))
                ts.append(tg.create_task(cf_r(12, 10), name="C10"))

        assert ts[4].result() == 4
        assert ts[5].result() == 5
        assert ts[8].result() == 8

        assert ts[9].state() is TaskState.CANCELLED
        assert ts[10].state() is TaskState.CANCELLED

        exc = ts[6].exception()
        assert isinstance(exc, ArithmeticError) and exc.args == (6,)
        exc = ts[7].exception()
        assert isinstance(exc, ArithmeticError) and exc.args == (7,)

        excs = e.value.args[1]
        assert [type(exc) for exc in excs] == [ArithmeticError, ArithmeticError]
        assert [exc.args for exc in excs] == [(6,), (7,)]

        logger.info("exit")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP4
