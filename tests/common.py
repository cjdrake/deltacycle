"""TODO(cjdrake): Write docstring."""

from deltacycle import Singular, resume


class Bool(Singular):
    """Variable that supports dumping to memory."""

    def __init__(self):
        super().__init__(value=False)

    def is_posedge(self) -> bool:
        return not self._prev and self._next

    def is_negedge(self) -> bool:
        return self._prev and not self._next

    def is_edge(self) -> bool:
        return self.is_posedge() or self.is_negedge()

    async def posedge(self):
        await resume((self, self.is_posedge))

    async def negedge(self):
        await resume((self, self.is_negedge))

    async def edge(self):
        await resume((self, self.is_edge))
