"""Delta Cycle

Credit to David Beazley's "Build Your Own Async" tutorial for inspiration:
https://www.youtube.com/watch?v=Y4Gt3Xjd7G8
"""

import logging
from logging import Filter, LogRecord

from ._event import Event
from ._kernel import Kernel, finish
from ._queue import Queue
from ._semaphore import BoundedSemaphore, Lock, Semaphore
from ._task import (
    AwaitableIf,
    AwaitList,
    Interrupt,
    Signal,
    Task,
    TaskCoro,
    TaskGroup,
)
from ._top import (
    any_var,
    create_task,
    get_current_task,
    get_kernel,
    get_running_kernel,
    now,
    run,
    set_kernel,
    sleep,
    step,
)
from ._variable import Aggregate, AggrItem, AggrValue, Predicate, Singular, Value, Variable

# Customize logging
logger = logging.getLogger(__name__)


class DeltaCycleFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
        try:
            kernel = get_running_kernel()
        except RuntimeError:
            record.time = -1
            record.taskName = None
        else:
            record.time = kernel.time()
            record.taskName = kernel.task().name
        return True


logger.addFilter(DeltaCycleFilter())


__all__ = [
    # kernel
    "Kernel",
    "finish",
    "get_running_kernel",
    "get_kernel",
    "set_kernel",
    "run",
    "step",
    "now",
    "sleep",
    # event
    "Event",
    # queue
    "Queue",
    # semaphore
    "Semaphore",
    "BoundedSemaphore",
    "Lock",
    # task
    "TaskCoro",
    "Signal",
    "Interrupt",
    "AwaitableIf",
    "AwaitList",
    "Task",
    "TaskGroup",
    "create_task",
    "get_current_task",
    # variable
    "Predicate",
    "Variable",
    "Value",
    "Singular",
    "Aggregate",
    "AggrItem",
    "AggrValue",
    "any_var",
]
