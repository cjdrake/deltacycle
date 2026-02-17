"""Test deltacycle.Container"""

import pytest

from deltacycle import Container, TaskGroup, run, sleep

from .conftest import trace


def test_len():
    async def main():
        container = Container(capacity=10)
        assert container.capacity == 10
        assert len(container) == 0
        await container.put(1)
        assert len(container) == 1
        await container.put(2)
        assert len(container) == 3
        assert container
        await container.get(1)
        assert len(container) == 2
        await container.get(2)
        assert len(container) == 0
        assert not container

    run(main())


EXP1 = {
    # P1
    (0, "P1", "PUT"),
    (1, "P1", "PUT"),
    (2, "P1", "PUT"),
    (3, "P1", "PUT"),
    (4, "P1", "PUT"),
    (5, "P1", "PUT"),
    (6, "P1", "PUT"),
    (7, "P1", "PUT"),
    (8, "P1", "PUT"),
    (9, "P1", "PUT"),
    (10, "P1", "PUT"),
    (11, "P1", "PUT"),
    (12, "P1", "PUT"),
    (14, "P1", "PUT"),
    (15, "P1", "PUT"),
    (16, "P1", "PUT"),
    # P2
    (0, "P2", "PUT"),
    (1, "P2", "PUT"),
    (3, "P2", "PUT"),
    (4, "P2", "PUT"),
    (5, "P2", "PUT"),
    (7, "P2", "PUT"),
    (8, "P2", "PUT"),
    (10, "P2", "PUT"),
    (11, "P2", "PUT"),
    (12, "P2", "PUT"),
    (13, "P2", "PUT"),
    (14, "P2", "PUT"),
    # C1
    (0, "C1", "GET"),
    (1, "C1", "GET"),
    (2, "C1", "GET"),
    (3, "C1", "GET"),
    (4, "C1", "GET"),
    (5, "C1", "GET"),
    (6, "C1", "GET"),
    (7, "C1", "GET"),
    (8, "C1", "GET"),
    (9, "C1", "GET"),
    (10, "C1", "GET"),
    (11, "C1", "GET"),
    (12, "C1", "GET"),
    (13, "C1", "GET"),
    (14, "C1", "GET"),
    (15, "C1", "GET"),
    # C2
    (0, "C2", "GET"),
    (1, "C2", "GET"),
    (2, "C2", "GET"),
    (3, "C2", "GET"),
    (4, "C2", "GET"),
    (5, "C2", "GET"),
    (6, "C2", "GET"),
    (7, "C2", "GET"),
    (8, "C2", "GET"),
    (9, "C2", "GET"),
    (10, "C2", "GET"),
    (11, "C2", "GET"),
    (12, "C2", "GET"),
    (13, "C2", "GET"),
    (14, "C2", "GET"),
    (15, "C2", "GET"),
    # C3
    (0, "C3", "GET"),
    (1, "C3", "GET"),
    (3, "C3", "GET"),
    (4, "C3", "GET"),
    (5, "C3", "GET"),
    (6, "C3", "GET"),
    (7, "C3", "GET"),
    (8, "C3", "GET"),
    (9, "C3", "GET"),
    (10, "C3", "GET"),
    (11, "C3", "GET"),
    (12, "C3", "GET"),
    (13, "C3", "GET"),
    (14, "C3", "GET"),
    (15, "C3", "GET"),
    (16, "C3", "GET"),
}


def test_prod_cons1(captrace: set[tuple[int, str, str]]):
    async def p(container: Container, n: int):
        for _ in range(16):
            await container.put(n)
            trace("PUT")
            await sleep(1)

    async def c(container: Container, n: int):
        for _ in range(16):
            await container.get(n)
            trace("GET")
            await sleep(1)

    async def main():
        container = Container(capacity=10)

        async with TaskGroup() as tg:
            tg.create_task(p(container, 5), name="P1")
            tg.create_task(p(container, 7), name="P2")
            tg.create_task(c(container, 2), name="C1")
            tg.create_task(c(container, 3), name="C2")
            tg.create_task(c(container, 5), name="C3")

    run(main())

    assert captrace == EXP1


EXP2 = {
    # P1
    (0, "P1", "PUT"),
    (1, "P1", "PUT"),
    (2, "P1", "PUT"),
    (3, "P1", "PUT"),
    (4, "P1", "PUT"),
    (5, "P1", "PUT"),
    (6, "P1", "PUT"),
    (7, "P1", "PUT"),
    # P2
    (0, "P2", "PUT"),
    (1, "P2", "PUT"),
    (2, "P2", "PUT"),
    (3, "P2", "PUT"),
    (4, "P2", "PUT"),
    (5, "P2", "PUT"),
    (6, "P2", "PUT"),
    # P3
    (8, "P3", "PUT"),
    (9, "P3", "PUT"),
    (10, "P3", "PUT"),
    (11, "P3", "PUT"),
    (12, "P3", "PUT"),
    (13, "P3", "PUT"),
    (14, "P3", "PUT"),
    (15, "P3", "PUT"),
    # C1
    (0, "C1", "GET"),
    (1, "C1", "GET"),
    (2, "C1", "GET"),
    (3, "C1", "GET"),
    (4, "C1", "GET"),
    (5, "C1", "GET"),
    (6, "C1", "GET"),
    (7, "C1", "GET"),
    # C2
    (0, "C2", "GET"),
    (1, "C2", "GET"),
    (2, "C2", "GET"),
    (3, "C2", "GET"),
    (4, "C2", "GET"),
    (5, "C2", "GET"),
    (6, "C2", "GET"),
    (7, "C2", "GET"),
    # C3
    (7, "P2", "PUT"),
    (8, "C3", "GET"),
    (9, "C3", "GET"),
    (10, "C3", "GET"),
    (11, "C3", "GET"),
    (12, "C3", "GET"),
    (13, "C3", "GET"),
    (14, "C3", "GET"),
    (15, "C3", "GET"),
}


def test_prod_cons2(captrace: set[tuple[int, str, str]]):
    async def p(container: Container, n: int):
        for _ in range(8):
            while not container.try_put(n):
                await sleep(1)
            trace("PUT")
            await sleep(1)

    async def c(container: Container, n: int):
        for _ in range(8):
            while not container.try_get(n):
                await sleep(1)
            trace("GET")
            await sleep(1)

    async def main():
        container = Container(capacity=8)

        async with TaskGroup() as tg:
            tg.create_task(p(container, 2), name="P1")
            tg.create_task(p(container, 3), name="P2")
            tg.create_task(p(container, 5), name="P3")
            tg.create_task(c(container, 2), name="C1")
            tg.create_task(c(container, 3), name="C2")
            tg.create_task(c(container, 5), name="C3")

    run(main())

    assert captrace == EXP2


def test_put_get_value_errors():
    async def main():
        container = Container(capacity=42)
        with pytest.raises(ValueError):
            await container.put(0)
        with pytest.raises(ValueError):
            await container.put(43)
        with pytest.raises(ValueError):
            container.try_get(0)
        with pytest.raises(ValueError):
            container.try_get(43)
        with pytest.raises(ValueError):
            await container.get(0)
        with pytest.raises(ValueError):
            await container.get(43)

    run(main())
