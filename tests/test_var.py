"""Test variables"""

import logging

from deltacycle import Singular, create_task, run, sleep

logger = logging.getLogger("deltacycle")


def test_var_await():
    x = Singular(value=0)
    x2 = Singular(value=0)
    x4 = Singular(value=0)
    x8 = Singular(value=0)

    async def cf(y: Singular, x: Singular):
        while True:
            _ = await x
            y.next = 2 * x.value

    async def main():
        create_task(cf(x2, x))
        create_task(cf(x4, x2))
        create_task(cf(x8, x4))

        for i in range(100):
            await sleep(1)
            x.next = i
            await sleep(1)
            assert x8.value == i * 8

    run(main())
