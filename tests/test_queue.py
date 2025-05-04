"""Test deltacycle.queue"""

import logging

from deltacycle import Queue, create_task, run, sleep

logger = logging.getLogger("deltacycle")


EXP = {
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


def test_prod_cons(caplog):
    caplog.set_level(logging.INFO, logger="deltacycle")

    q = Queue()
    assert q.maxsize == 0

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
    assert msgs == EXP
