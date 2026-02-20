.. _tutorial:

################
    Tutorial
################

To work through the example code in this chapter,
you need to install Python and DeltaCycle.

See :ref:`installation` for details.


Hello World
===========

For DeltaCycle, the simplest program to print "Hello, world!" is:

.. code-block:: python

    from deltacycle import run

    async def main():
        print("Hello, world!")

    run(main())

The ``async def main(): ...`` code block declares a *coroutine function*.
The ``run`` function wraps an instance of the ``main`` coroutine in a *task*,
and schedules that task to execute as soon as possible.

See `Coroutines <https://docs.python.org/3/library/asyncio-task.html#coroutine>`_
in the official Python documentation for background.
