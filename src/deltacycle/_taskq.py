"""Task priority queue"""

import heapq
from collections.abc import Generator
from typing import Any

from ._task import Task

type Item = tuple[int, Task, Any]


class TaskQueue:
    """Priority queue for ordering task execution."""

    def __init__(self):
        # time, region, index, task, value
        self._items: list[tuple[int, int, int, Task, Any]] = []

        # Monotonically increasing integer
        # Breaks (time, region, ...) ties in the heapq
        self._index: int = 0

    def __bool__(self) -> bool:
        return bool(self._items)

    # def clear(self):
    #    self._items.clear()
    #    self._index = 0

    def push(self, time: int, task: Task, value: Any = None):
        item = (time, task.region, self._index, task, value)
        heapq.heappush(self._items, item)
        self._index += 1

    def peek(self) -> Item:
        time, _, _, task, value = self._items[0]
        return (time, task, value)

    def pop(self) -> Item:
        time, _, _, task, value = heapq.heappop(self._items)
        return (time, task, value)

    def iter_time(self) -> Generator[Item, None, None]:
        item = self.pop()
        yield item
        while self._items and self._items[0][0] == item[0]:
            yield self.pop()

    def drop(self, task: Task):
        for i, (_, _, _, t, _) in enumerate(self._items):
            if t is task:
                index = i
                break
        else:
            assert False  # pragma: no cover
        self._items.pop(index)
