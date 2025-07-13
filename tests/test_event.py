"""Test deltacycle.Event"""

import logging

from pytest import LogCaptureFixture

from deltacycle import AnyOf, Event, create_task, get_running_kernel, now, run, sleep

logger = logging.getLogger("deltacycle")


async def primary(event: Event):
    logger.info("enter")

    await sleep(10)

    # T=10
    logger.info("set")
    event.set()
    assert event

    await sleep(10)

    # T=20
    logger.info("clear")
    event.clear()
    assert not event

    await sleep(10)

    # T=30
    logger.info("set")
    event.set()
    assert event

    logger.info("exit")


async def secondary(event: Event):
    logger.info("enter")

    # Event clear
    logger.info("waiting")
    await event

    # Event set @10
    logger.info("running")
    await sleep(10)

    # Event clear
    logger.info("waiting")
    await event

    # Event set @30
    logger.info("running")
    await sleep(10)

    # Event still set: return immediately
    await event

    logger.info("exit")


EXP1 = {
    # P
    (0, "P", "enter"),
    (10, "P", "set"),
    (20, "P", "clear"),
    (30, "P", "set"),
    (30, "P", "exit"),
    # S1
    (0, "S1", "enter"),
    (0, "S1", "waiting"),
    (10, "S1", "running"),
    (20, "S1", "waiting"),
    (30, "S1", "running"),
    (40, "S1", "exit"),
    # S2
    (0, "S2", "enter"),
    (0, "S2", "waiting"),
    (10, "S2", "running"),
    (20, "S2", "waiting"),
    (30, "S2", "running"),
    (40, "S2", "exit"),
    # S3
    (0, "S3", "enter"),
    (0, "S3", "waiting"),
    (10, "S3", "running"),
    (20, "S3", "waiting"),
    (30, "S3", "running"),
    (40, "S3", "exit"),
}


def test_acquire_release(caplog: LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="deltacycle")

    async def main():
        event = Event()
        create_task(primary(event), name="P")
        create_task(secondary(event), name="S1")
        create_task(secondary(event), name="S2")
        create_task(secondary(event), name="S3")

    run(main())

    msgs = {(r.time, r.taskName, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


def test_serial():
    async def sleep_set(e: Event, t: int):
        await sleep(t)
        e.set()

    async def main():
        e0 = Event()
        e1 = Event()
        e2 = Event()

        create_task(sleep_set(e0, 10), name="first")
        create_task(sleep_set(e1, 20), name="second")
        create_task(sleep_set(e2, 30), name="third")

        e: Event = await e0
        assert e is e0 and now() == 10
        e: Event = await e1
        assert e is e1 and now() == 20
        e: Event = await e2
        assert e is e2 and now() == 30

    run(main())


def test_list_any_list():
    async def sleep_set(t: int, e: Event):
        await sleep(t)
        e.set()

    async def main():
        e10 = Event()
        e20 = Event()
        e30 = Event()

        create_task(sleep_set(10, e10), name="e10")
        create_task(sleep_set(20, e20), name="e20")
        create_task(sleep_set(30, e30), name="e30")

        e = await AnyOf(e10, e20, e30)
        assert e is e10

        kernel = get_running_kernel()
        assert not kernel._task_deps

    run(main())


def test_list_any_one_set():
    async def sleep_set(t: int, e: Event):
        await sleep(t)
        e.set()

    async def main():
        e10 = Event()
        e20 = Event()
        e30 = Event()

        e20.set()

        create_task(sleep_set(10, e10), name="e10")
        create_task(sleep_set(20, e20), name="e20")
        create_task(sleep_set(30, e30), name="e30")

        e = await AnyOf(e10, e20, e30)
        assert e is e20
        assert now() == 0

        kernel = get_running_kernel()
        assert not kernel._task_deps

    run(main())
