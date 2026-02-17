"""Hello, world!"""

import pytest

from deltacycle import Kernel, get_kernel, run, sleep

from .conftest import trace

EXP = {
    (-1, "", "Before Time"),
    (2, "main", "Hello"),
    (4, "main", "World"),
}


def test_hello(captrace: set[tuple[int, str, str]]):
    """Test basic async/await hello world functionality."""
    trace("Before Time")

    async def hello():
        await sleep(2)
        trace("Hello")
        await sleep(2)
        trace("World")
        return 42

    ret = run(hello())
    assert ret == 42

    kernel = get_kernel()
    assert kernel is not None
    assert kernel.state() is Kernel.State.COMPLETED

    with pytest.raises(RuntimeError):
        run(kernel=kernel)

    assert captrace == EXP
