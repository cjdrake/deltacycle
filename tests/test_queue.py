"""Test deltacycle.queue"""

import logging

from deltacycle import Queue, create_task, run, sleep

logger = logging.getLogger("deltacycle")


EXP1 = {
    (0, "Producing: 0"),
    (0, "Consuming: 0"),
    (10, "Producing: 1"),
    (10, "Consuming: 1"),
    (20, "Producing: 2"),
    (20, "Consuming: 2"),
    (30, "Producing: 3"),
    (30, "Consuming: 3"),
    (40, "Producing: 4"),
    (40, "Consuming: 4"),
    (50, "Producing: 5"),
    (50, "Consuming: 5"),
    (60, "Producing: 6"),
    (60, "Consuming: 6"),
    (70, "Producing: 7"),
    (70, "Consuming: 7"),
    (80, "Producing: 8"),
    (80, "Consuming: 8"),
    (90, "Producing: 9"),
    (90, "Consuming: 9"),
    (100, "Producer: CLOSED"),
}


def test_prod_cons1(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    q = Queue()
    assert q.cap == 0

    async def prod():
        for i in range(10):
            logger.info("Producing: %d", i)
            await q.put(i)
            await sleep(10)
        logger.info("Producer: CLOSED")

    async def cons():
        while True:
            i = await q.get()
            logger.info("Consuming: %d", i)

    async def main():
        create_task(prod())
        create_task(cons())

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP1


EXP2 = {
    (0, "Producing: 0"),
    (0, "Producing: 1"),
    (0, "Producing: 2"),
    (10, "Consuming: 0"),
    (10, "Producing: 3"),
    (20, "Consuming: 1"),
    (20, "Producing: 4"),
    (30, "Consuming: 2"),
    (30, "Producing: 5"),
    (40, "Consuming: 3"),
    (40, "Producing: 6"),
    (50, "Consuming: 4"),
    (50, "Producing: 7"),
    (60, "Consuming: 5"),
    (60, "Producing: 8"),
    (70, "Consuming: 6"),
    (70, "Producing: 9"),
    (80, "Consuming: 7"),
    (80, "Producer: CLOSED"),
    (90, "Consuming: 8"),
    (100, "Consuming: 9"),
}


def test_prod_cons2(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    q = Queue(2)
    assert q.cap == 2

    async def prod():
        for i in range(10):
            logger.info("Producing: %d", i)
            await q.put(i)
        logger.info("Producer: CLOSED")

    async def cons():
        while True:
            await sleep(10)
            i = await q.get()
            logger.info("Consuming: %d", i)

    async def main():
        create_task(prod())
        create_task(cons())

    run(main())

    msgs = {(r.time, r.getMessage()) for r in caplog.records}
    assert msgs == EXP2


def test_prod_cons3():
    q = Queue(2)
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
