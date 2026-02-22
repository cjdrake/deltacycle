.. _tutorial:

################
    Tutorial
################


Prerequisites
=============

To work through the example code in this chapter,
first install `Python <https://www.python.org>`_ and DeltaCycle.

See :ref:`installation` for how to install DeltaCycle.

For brevity,
all code examples assume you have executed the following prelude:

.. code-block:: python

    from deltacycle import *


Hello World
===========

For DeltaCycle, the simplest program to print "Hello, world!" is:

.. code-block:: python

    async def main():
        print("Hello, world!")

    run(main())

The ``async def main(): ...`` code block declares a *coroutine function*.
The ``run`` function wraps an instance of the ``main`` coroutine in a *task*,
and schedules that task to execute as soon as possible.

Output::

    Hello, world!

See `Coroutines <https://docs.python.org/3/library/asyncio-task.html#coroutine>`_
in the official Python documentation for background.


Consuming Time
==============

A simulation is a model of how a system's state evolves over time.
DeltaCycle coroutines simulate the passage of time with the ``sleep`` function.
The ``now`` function returns the current simulation time,
which can be handy for debug, measurement, and analysis.

.. code-block:: python

    async def main():
        print(now(), "Enter")
        await sleep(1)
        print(now(), "foo")
        await sleep(1)
        print(now(), "bar")
        await sleep(1)
        print(now(), "Exit")

    run(main())

The ``main`` coroutine executes four ``print`` statements,
each separated by one unit of time.
The simulation clock starts at time ``0``.

Output::

    0 Enter
    1 foo
    2 bar
    3 Exit
