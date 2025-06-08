"""Common simulation data types"""

import logging

from deltacycle import Aggregate, Singular, touched

logger = logging.getLogger("deltacycle")


class Bool(Singular):
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
        await touched({self: self.is_posedge})

    async def negedge(self):
        await touched({self: self.is_negedge})

    async def edge(self):
        await touched({self: self.is_edge})


class Int(Singular):
    def __init__(self, name: str):
        super().__init__(value=int())
        self._name = name


class IntMem(Aggregate):
    def __init__(self, name: str):
        super().__init__(value=int())
        self._name = name
