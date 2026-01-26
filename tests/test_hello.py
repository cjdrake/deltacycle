"""Hello, world!"""

import pytest
from pytest import CaptureFixture

from deltacycle import Kernel, get_kernel, run, sleep

from .common import tprint

EXP = """\
[  -1] Before Time
[   2] Hello
[   4] World
"""


def test_hello(capsys: CaptureFixture[str]):
    """Test basic async/await hello world functionality."""
    tprint("Before Time")

    async def hello():
        await sleep(2)
        tprint("Hello")
        await sleep(2)
        tprint("World")
        return 42

    ret = run(hello())
    assert ret == 42

    kernel = get_kernel()
    assert kernel is not None
    assert kernel.state() is Kernel.State.COMPLETED

    with pytest.raises(RuntimeError):
        run(kernel=kernel)

    cap = capsys.readouterr()
    assert cap.out == EXP
