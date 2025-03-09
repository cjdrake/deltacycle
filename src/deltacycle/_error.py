"""Error classes"""


class CancelledError(Exception):
    """Task has been cancelled."""


class FinishError(Exception):
    """Force the simulation to stop."""


class InvalidStateError(Exception):
    """Task has an invalid state."""
