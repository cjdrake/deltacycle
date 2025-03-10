"""TODO(cjdrake): Write docstring."""

# pylint: disable=protected-access

from __future__ import annotations

from abc import ABC
from collections import defaultdict
from collections.abc import Awaitable, Generator, Hashable


def _loop():
    from ._sim import get_running_loop  # pylint: disable=import-outside-toplevel

    return get_running_loop()


class Variable(Awaitable):
    """Model component."""

    def __await__(self) -> Generator[None, Variable, Variable]:
        loop = _loop()
        loop.state_wait(self, self.changed)

        # Suspend
        x = yield
        assert x is self

        # Resume
        return x

    present = property(fget=lambda self: NotImplemented)

    def changed(self) -> bool:
        raise NotImplementedError()  # pragma: no cover

    def update(self):
        raise NotImplementedError()  # pragma: no cover


class Value(ABC):
    """Variable value."""

    def _get_value(self):
        raise NotImplementedError()  # pragma: no cover

    value = property(fget=_get_value)

    def _set_next(self, value):
        raise NotImplementedError()  # pragma: no cover

    next = property(fset=_set_next)


class Singular(Variable, Value):
    """Model state organized as a single unit."""

    def __init__(self, value):
        Variable.__init__(self)
        self._value = value
        self._next_value = value
        self._changed = False

    # Value
    def _get_value(self):
        return self._value

    value = property(fget=_get_value)

    def _set_next(self, value):
        self._changed = value != self._next_value
        self._next_value = value

        # Notify the event loop
        loop = _loop()
        loop.state_touch(self)

    next = property(fset=_set_next)

    # Variable
    def _get_present(self):
        return self._next_value

    present = property(fget=_get_present)

    def changed(self) -> bool:
        return self._changed

    def update(self):
        self._value = self._next_value
        self._changed = False

    # Other
    def dirty(self) -> bool:
        return self._next_value != self._value


class Aggregate(Variable):
    """Model state organized as multiple units."""

    def __init__(self, value):
        Variable.__init__(self)
        self._values = defaultdict(lambda: value)
        self._next_values = dict()

    # [key] => Value
    def __getitem__(self, key: Hashable) -> AggrValue:
        return AggrValue(self, key)

    def _get_value(self, key: Hashable):
        return self._values[key]

    def _get_next_value(self, key: Hashable):
        try:
            return self._next_values[key]
        except KeyError:
            return self._values[key]

    def _set_next(self, key: Hashable, value):
        if value != self._get_next_value(key):
            self._next_values[key] = value

        # Notify the event loop
        loop = _loop()
        loop.state_touch(self)

    # Variable
    def _get_present(self) -> AggrPresent:
        return AggrPresent(self)

    present = property(fget=_get_present)

    def changed(self) -> bool:
        return bool(self._next_values)

    def update(self):
        while self._next_values:
            key, value = self._next_values.popitem()
            self._values[key] = value


class AggrPresent:
    """Wrap Aggregate present value."""

    def __init__(self, aggr: Aggregate):
        self._aggr = aggr

    def __getitem__(self, key: Hashable):
        return self._aggr._get_next_value(key)


class AggrValue(Value):
    """Wrap Aggregate value getter/setter."""

    def __init__(self, aggr: Aggregate, key: Hashable):
        self._aggr = aggr
        self._key = key

    def _get_value(self):
        return self._aggr._get_value(self._key)

    value = property(fget=_get_value)

    def _set_next(self, value):
        self._aggr._set_next(self._key, value)

    next = property(fset=_set_next)
