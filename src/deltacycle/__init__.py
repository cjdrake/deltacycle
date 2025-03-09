"""Delta Cycle"""

import logging
from logging import Filter, LogRecord

from ._sim import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    FIRST_EXCEPTION,
    Aggregate,
    BoundedSemaphore,
    CancelledError,
    Event,
    EventLoop,
    FinishError,
    InvalidStateError,
    Lock,
    Semaphore,
    Singular,
    State,
    Task,
    TaskGroup,
    TaskState,
    Value,
    changed,
    create_task,
    del_event_loop,
    finish,
    get_event_loop,
    get_running_loop,
    irun,
    new_event_loop,
    now,
    resume,
    run,
    set_event_loop,
    sleep,
    wait,
)

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
    "FinishError",
    "InvalidStateError",
    # state
    "State",
    "Value",
    "Singular",
    "Aggregate",
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
    # event_loop
    "EventLoop",
    "get_running_loop",
    "get_event_loop",
    "set_event_loop",
    "new_event_loop",
    "del_event_loop",
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
