"""Delta Cycle"""

import logging
from logging import Filter, LogRecord

from ._error import CancelledError, InvalidStateError
from ._sim import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    FIRST_EXCEPTION,
    BoundedSemaphore,
    Event,
    Lock,
    Loop,
    Semaphore,
    Task,
    TaskGroup,
    TaskState,
    changed,
    create_task,
    finish,
    get_loop,
    get_running_loop,
    irun,
    now,
    resume,
    run,
    set_loop,
    sleep,
    wait,
)
from ._variable import Aggregate, AggrItem, AggrValue, Singular, Value, Variable

# Customize logging
logger = logging.getLogger(__name__)


class DeltaCycleFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
        loop = get_running_loop()
        record.time = loop.time()
        return True


logger.addFilter(DeltaCycleFilter())


__all__ = [
    # error
    "CancelledError",
    "InvalidStateError",
    # variable
    "Variable",
    "Value",
    "Singular",
    "Aggregate",
    "AggrItem",
    "AggrValue",
    # task
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
    # loop
    "Loop",
    "get_running_loop",
    "get_loop",
    "set_loop",
    "now",
    "run",
    "irun",
    "finish",
    "sleep",
    "changed",
    "resume",
    # wait
    "FIRST_COMPLETED",
    "FIRST_EXCEPTION",
    "ALL_COMPLETED",
    "wait",
]
