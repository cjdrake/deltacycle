# Delta Cycle

DeltaCycle is a Python library for discrete event simulation (DES).
Processes are described by `async def` coroutine functions,
and concurrency is implemented using `async / await` statements.

In DES, the simulation is subdivided into sequential slots.
Each slot is assigned a monotonically increasing integer value, called "time".
Multiple events may happen during each time slot.
Those events will trigger tasks that execute in zero time,
which may schedule additional events for present or future time slots.
The term "delta cycle" refers to a zero-delay subdivision of a time slot.

DeltaCycle implements a fixed-priority task scheduling algorithm.
This allows fine-grain control over the task execution order from simultaneous events.

[Read the docs!](https://deltacycle.rtfd.org) (WIP)

[![Documentation Status](https://readthedocs.org/projects/deltacycle/badge/?version=latest)](https://deltacycle.readthedocs.io/en/latest/?badge=latest)

## Features

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
