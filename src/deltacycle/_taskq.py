"""Task priority queue"""

import heapq
from typing import Any

from ._task import Task


class TaskQueue:
    """Priority queue for ordering task execution."""

    def __init__(self):
        # time, priority, index, task, value
        self._items: list[tuple[int, int, int, Task, Any]] = []

        # Monotonically increasing integer
        # Breaks (time, priority, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    def clear(self):
        self._items.clear()
        self._index = 0

    def push(self, time: int, task: Task, value: Any = None):
        item = (time, task.priority, self._index, task, value)
        heapq.heappush(self._items, item)
        self._index += 1

    def peek(self) -> int:
        return self._items[0][0]

    def pop(self) -> tuple[Task, Any]:
        _, _, _, task, value = heapq.heappop(self._items)
        return (task, value)

    def drop(self, task: Task):
        for i, (_, _, _, t, _) in enumerate(self._items):
            if t is task:
                index = i
                break
        else:
            assert False  # pragma: no cover
        self._items.pop(index)
