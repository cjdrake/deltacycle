"""Test deltacycle.TaskGroup"""

import logging

import pytest
from pytest import LogCaptureFixture

from deltacycle import Task, TaskGroup, run, sleep

logger = logging.getLogger("deltacycle")


async def group_coro(t: int, r: int):
    logger.info("enter")
    await sleep(t)
    logger.info("exit")
    return r


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
            ts.append(tg.create_task(group_coro(5, 0), name="C0"))
            ts.append(tg.create_task(group_coro(10, 1), name="C1"))
            ts.append(tg.create_task(group_coro(10, 2), name="C2"))
            ts.append(tg.create_task(group_coro(15, 3), name="C3"))

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


async def group_coro_exc(t: int, r: int):
    logger.info("enter")
    await sleep(t)
    raise ArithmeticError(r)


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

                # These tasks will complete successfully
                ts.append(tg.create_task(group_coro(5, 0), name="C0"))
                ts.append(tg.create_task(group_coro(10, 1), name="C1"))
                # These tasks will raise an exception
                ts.append(tg.create_task(group_coro_exc(10, 2), name="C2"))
                ts.append(tg.create_task(group_coro_exc(10, 3), name="C3"))
                # This task will also complete successfully
                # (It completes before cancellation takes effect)
                ts.append(tg.create_task(group_coro(10, 4), name="C4"))
                # These tasks will be cancelled
                ts.append(tg.create_task(group_coro(11, 5), name="C5"))
                ts.append(tg.create_task(group_coro(13, 6), name="C6"))
                ts.append(tg.create_task(group_coro(15, 7), name="C7"))

        assert ts[0].result() == 0
        assert ts[1].result() == 1
        assert ts[4].result() == 4

        assert ts[5].cancelled()
        assert ts[6].cancelled()
        assert ts[7].cancelled()

        exc = ts[2].exception()
        assert isinstance(exc, ArithmeticError) and exc.args == (2,)
        exc = ts[3].exception()
        assert isinstance(exc, ArithmeticError) and exc.args == (3,)

        assert e.value.args[0] == "errors"
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

                ts.append(tg.create_task(group_coro(5, 0), name="C0"))
                ts.append(tg.create_task(group_coro(10, 1), name="C1"))

                raise ArithmeticError(42)

        assert ts[0].cancelled()
        assert ts[1].cancelled()
        assert e.value.args == (42,)

        logger.info("exit")

    run(main())
    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP3
