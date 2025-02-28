"""TODO(cjdrake): Write docstring."""


class FinishError(Exception):
    """Force the simulation to stop."""


class InvalidStateError(Exception):
    """Task has an invalid state."""
