"""Delta Cycle

Credit to David Beazley's "Build Your Own Async" tutorial for inspiration:
https://www.youtube.com/watch?v=Y4Gt3Xjd7G8
"""

import logging
from logging import Filter, LogRecord

from ._event import Event
from ._loop import (
    Loop,
    LoopState,
    changed,
    create_task,
    finish,
    get_loop,
    get_running_loop,
    irun,
    now,
    run,
    set_loop,
    sleep,
    touched,
)
from ._queue import Queue
from ._semaphore import BoundedSemaphore, Lock, Semaphore
from ._task import CancelledError, InvalidStateError, Task, TaskState
from ._task_group import TaskGroup
from ._variable import Aggregate, AggrItem, AggrValue, Singular, Value, Variable

# Customize logging
logger = logging.getLogger(__name__)


class DeltaCycleFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
        record.time = now()
        return True


logger.addFilter(DeltaCycleFilter())


__all__ = [
    # variable
    "Variable",
    "Value",
    "Singular",
    "Aggregate",
    "AggrItem",
    "AggrValue",
    # task
    "CancelledError",
    "InvalidStateError",
    "Task",
    "TaskState",
    "TaskGroup",
    "create_task",
    # event
    "Event",
    # semaphore
    "Semaphore",
    "BoundedSemaphore",
    "Lock",
    # queue
    "Queue",
    # loop
    "Loop",
    "LoopState",
    "get_running_loop",
    "get_loop",
    "set_loop",
    "now",
    "run",
    "irun",
    "finish",
    "sleep",
    "changed",
    "touched",
]
