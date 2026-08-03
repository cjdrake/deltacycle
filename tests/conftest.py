"""PyTest Configuration"""

import pytest

from deltacycle import get_running_kernel

type TraceMsg = tuple[int, str, str]
type Trace = set[TraceMsg]

msgs: Trace = set()


def trace(msg: str = ""):
    try:
        kernel = get_running_kernel()
    except RuntimeError:
        time = -1
        task_name = ""
    else:
        time = kernel.time()
        task = kernel.check_task()
        task_name = task.name
    msgs.add((time, task_name, msg))


@pytest.fixture
def captrace():
    yield msgs
    msgs.clear()
