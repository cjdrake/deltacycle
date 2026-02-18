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
    * Credit Pools
    * Queues
    * Containers
* Structured Concurrency:
    * Task Groups (parent/child hierarchy)
    * Interrupts
    * Exceptions
* Model Variables:
    * Singular
    * Aggregate

## Example

The following code simulates singing in the round.
Four singers perform "Row, Row, Row Your Boat" in staggered fashion.
Each `singer` is represented by a coroutine.
A `separator` coroutine draws lines for readability.
The coroutines are wrapped by tasks,
and tasks are assigned a priority for precise ordering of concurrent events.

```pycon
>>> from deltacycle import *

>>> song = [
...     "Row, row, row your boat",
...     "Gently down the stream",
...     "Merrily, merrily, merrily, merrily",
...     "Life is but a dream",
... ]

>>> async def singer(name: str, delay: int = 0):
...     await sleep(delay)
...     for line in song:
...         print(f"{now()}  ♫ {name}: {line:34} ♫")
...         await sleep(1)

>>> async def separator():
...     while True:
...         print(f"{now()}  ♫---------------------------------------♫")
...         await sleep(1)

>>> async def main():
...     t = create_task(separator(), priority=-1)
...
...     async with TaskGroup() as tg:
...         tg.create_task(singer("A", delay=0), priority=1)
...         tg.create_task(singer("B", delay=1), priority=2)
...         tg.create_task(singer("C", delay=2), priority=3)
...         tg.create_task(singer("D", delay=3), priority=4)
...
...     t.interrupt()  # Interrupt separator task
...
...     return "Bow / Curtsy"

>>> r = run(main())
0  ♫---------------------------------------♫
0  ♫ A: Row, row, row your boat            ♫
1  ♫---------------------------------------♫
1  ♫ A: Gently down the stream             ♫
1  ♫ B: Row, row, row your boat            ♫
2  ♫---------------------------------------♫
2  ♫ A: Merrily, merrily, merrily, merrily ♫
2  ♫ B: Gently down the stream             ♫
2  ♫ C: Row, row, row your boat            ♫
3  ♫---------------------------------------♫
3  ♫ A: Life is but a dream                ♫
3  ♫ B: Merrily, merrily, merrily, merrily ♫
3  ♫ C: Gently down the stream             ♫
3  ♫ D: Row, row, row your boat            ♫
4  ♫---------------------------------------♫
4  ♫ B: Life is but a dream                ♫
4  ♫ C: Merrily, merrily, merrily, merrily ♫
4  ♫ D: Gently down the stream             ♫
5  ♫---------------------------------------♫
5  ♫ C: Life is but a dream                ♫
5  ♫ D: Merrily, merrily, merrily, merrily ♫
6  ♫---------------------------------------♫
6  ♫ D: Life is but a dream                ♫
7  ♫---------------------------------------♫

>>> r
'Bow / Curtsy'
```

## Installing

DeltaCycle is available on [PyPI](https://pypi.org):

    $ pip install deltacycle

It requires Python 3.12+

## Developing

DeltaCycle's repository is on [GitHub](https://github.com):

    $ git clone https://github.com/cjdrake/deltacycle.git

It is 100% Python, and has no runtime dependencies.
Development dependencies are listed in `requirements-dev.txt`.
