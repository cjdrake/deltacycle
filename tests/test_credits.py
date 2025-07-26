"""TODO(cjdrake): Write docstring."""

from deltacycle import CreditPool, run


def test_len():
    async def main():
        credits = CreditPool(capacity=10)
        assert len(credits) == 0
        credits.put(1)
        assert len(credits) == 1
        credits.put(2)
        assert len(credits) == 3
        assert credits
        await credits.get(1)
        assert len(credits) == 2
        await credits.get(2)
        assert len(credits) == 0
        assert not credits

    run(main())
