"""Common simulation data types"""

import logging

from deltacycle import Aggregate, Singular

logger = logging.getLogger("deltacycle")


class Bool(Singular[bool]):
    """Variable that supports dumping to memory."""

    def __init__(self, name: str):
        super().__init__(value=bool())
        self._name = name

    def is_posedge(self) -> bool:
        return not self._prev and self._next

    def is_negedge(self) -> bool:
        return self._prev and not self._next

    def is_edge(self) -> bool:
        return self.is_posedge() or self.is_negedge()

    async def posedge(self):
        await self.pred(self.is_posedge)

    async def negedge(self):
        await self.pred(self.is_negedge)

    async def edge(self):
        await self.pred(self.is_edge)


class Int(Singular[int]):
    def __init__(self, name: str):
        super().__init__(value=int())
        self._name = name


class IntMem(Aggregate[int]):
    def __init__(self, name: str):
        super().__init__(value=int())
        self._name = name
