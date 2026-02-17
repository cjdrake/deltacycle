"""Test seqlogic.sim.Lock class."""

from deltacycle import Lock, create_task, run, sleep

from .conftest import trace


async def use_acquire_release(lock: Lock, t1: int, t2: int):
    trace("enter")

    await sleep(t1)

    trace("attempt get")
    await lock.get()
    trace("acquired")

    try:
        await sleep(t2)
    finally:
        trace("put")
        lock.put()

    await sleep(10)
    trace("exit")


async def use_with(lock: Lock, t1: int, t2: int):
    trace("enter")

    await sleep(t1)

    trace("attempt get")
    async with lock.req():
        trace("acquired")
        await sleep(t2)
    trace("put")

    await sleep(10)
    trace("exit")


EXP = {
    (0, "0", "enter"),
    (0, "1", "enter"),
    (0, "2", "enter"),
    (0, "3", "enter"),
    (10, "0", "attempt get"),
    (10, "0", "acquired"),
    (11, "1", "attempt get"),
    (12, "2", "attempt get"),
    (13, "3", "attempt get"),
    (20, "0", "put"),
    (20, "1", "acquired"),
    (30, "0", "exit"),
    (30, "1", "put"),
    (30, "2", "acquired"),
    (40, "1", "exit"),
    (40, "2", "put"),
    (40, "3", "acquired"),
    (50, "2", "exit"),
    (50, "3", "put"),
    (60, "3", "exit"),
}


def test_acquire_release(captrace: set[tuple[int, str, str]]):
    async def main():
        lock = Lock()
        for i in range(4):
            create_task(use_acquire_release(lock, i + 10, 10), name=f"{i}")

    run(main())

    assert captrace == EXP


def test_async_with(captrace: set[tuple[int, str, str]]):
    async def main():
        lock = Lock()
        for i in range(4):
            create_task(use_with(lock, i + 10, 10), name=f"{i}")

    run(main())

    assert captrace == EXP
