# Delta Cycle

DeltaCycle is a Python library for discrete event simulation (DES).

A simulation has two components: a collection of *variables*,
and a collection of *tasks*.
Variables represent the instantaneous state of the simulation.
They may be organized into arbitrary data structures.
Tasks define how that state evolves.
They may appear concurrent, but are scheduled sequentially.

Task execution is subdivided into a sequence of slots.
Slots are assigned a monotonically increasing integer value, called *time*.
Multiple tasks may execute in the same slot, and therefore at the same time.
The term "delta cycle" refers to a zero-delay subdivision of a time slot.
It is the clockwork mechanism behind the illusion of concurrency.

[Read the docs!](https://deltacycle.rtfd.org) (WIP)

[![Documentation Status](https://readthedocs.org/projects/deltacycle/badge/?version=latest)](https://deltacycle.readthedocs.io/en/latest/?badge=latest)

## Features

* Kernel: task scheduler
* Task: coroutine wrapper
* Synchronization Primitives:
    * Events
    * Semaphores
    * Queues
* Structured Concurrency:
    * Task Groups (parent/child hierarchy)
    * Interrupts
    * Exceptions
* Model Variables:
    * Singular
    * Aggregate

## Example

The following code simulates two clocks running concurrently.
The *fast* clock prints the current time every time step.
The *slow* clock prints the current time every two time steps.

```python
>>> from deltacycle import create_task, now, run, sleep

>>> async def clock(name: str, period: int):
...     while True:
...         print(f"{now()}: {name}")
...         await sleep(period)

>>> async def main():
...     create_task(clock("fast", 1))
...     create_task(clock("slow", 2))

>>> run(main(), until=7)
0: fast
0: slow
1: fast
2: slow
2: fast
3: fast
4: slow
4: fast
5: fast
6: slow
6: fast
```

## Installing

DeltaCycle is available on [PyPI](https://pypi.org):

    $ pip install deltacycle

It supports Python 3.12+

## Developing

DeltaCycle's repository is on [GitHub](https://github.com):

    $ git clone https://github.com/cjdrake/deltacycle.git

It is 100% Python, and has no runtime dependencies.
Development dependencies are listed in `requirements-dev.txt`.
