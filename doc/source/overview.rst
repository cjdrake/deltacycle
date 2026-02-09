.. _overview:

################
    Overview
################

DeltaCycle is a Python library for discrete event simulation (DES).
Using the intuitive `async / await <https://peps.python.org/pep-0492/>`_ syntax,
it provides a natural language for modeling complex systems to solve real-world problems.

To appropriate a familiar aphorism, it's DES for humans.

A simulation has two components:

* a collection of *variables*
* a collection of *tasks*

Variables represent the instantaneous state of the simulation.
They may be organized into arbitrary data structures.

Tasks define how the simulation state evolves.
They may appear concurrent, but are scheduled sequentially.

DeltaCycle's simulation kernel was designed to support a range of scheduling semantics,
from the fine-grained inter-timeslot "delta cycle" ordering of digital logic events,
to the relatively coarse-grained requirements of industrial engineering and operations research.

The `SimPy example <https://simpy.readthedocs.io/en/latest/>`_
of two clocks ticking at different intervals looks like this using DeltaCycle:

.. code-block:: python

    >>> from deltacycle import now, sleep

    >>> async def clock(name: str, period: int):
    ...     while True:
    ...         print(name, now() / 10.0)
    ...         await sleep(period)

    >>> async def main():
    ...     create_task(clock("fast", 5))
    ...     create_task(clock("slow", 10))

Notice the replacement of ``def`` with ``async def``, and ``yield`` with ``await``.

Simulations can be called to run as fast as possible:

.. code-block:: python

    >>> from deltacycle import run
    >>> run(main(), until=20)
    fast 0.0
    slow 0.0
    fast 0.5
    slow 1.0
    fast 1.0
    fast 1.5

Or they can be iterated one step at a time:

.. code-block:: python

    >>> from deltacycle import step
    >>> g = step(main())
    >>> next(g)
    0
    >>> next(g)
    fast 0.0
    slow 0.0
    5
    >>> next(g)
    fast 0.5
    10
    >>> next(g)
    slow 1.0
    fast 1.0
    15
    >>> next(g)
    fast 1.5
    20
