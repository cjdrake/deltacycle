"""Delta Cycle"""

import logging
from logging import Filter, LogRecord

from ._error import FinishError, InvalidStateError
from ._loop import (
    Loop,
    create_task,
    finish,
    get_loop,
    get_running_loop,
    irun,
    model_wait,
    now,
    run,
    set_loop,
    sleep,
)
from ._task import Task, TaskState
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
    "FinishError",
    "InvalidStateError",
    # variable
    "Variable",
    "Value",
    "Singular",
    "Aggregate",
    "AggrValue",
    "AggrItem",
    # task
    "Task",
    "TaskState",
    "create_task",
    # event_loop
    "Loop",
    "get_running_loop",
    "get_loop",
    "set_loop",
    "now",
    "run",
    "irun",
    "finish",
    "sleep",
    "model_wait",
]
