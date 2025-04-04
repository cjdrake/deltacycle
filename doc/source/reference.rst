#################
    Reference
#################

Errors
======

.. autoexception:: deltacycle.CancelledError
.. autoexception:: deltacycle.FinishError
.. autoexception:: deltacycle.InvalidStateError

Variables
=========

.. autoclass:: deltacycle.Variable
    :show-inheritance:

    .. autoproperty:: value
    .. automethod:: changed
    .. automethod:: update

.. autoclass:: deltacycle.Value
    :show-inheritance:

    .. autoproperty:: prev
    .. autoproperty:: next

.. autoclass:: deltacycle.Singular
    :show-inheritance:

.. autoclass:: deltacycle.Aggregate
    :show-inheritance:

    .. automethod:: deltacycle.Aggregate.__getitem__

.. autoclass:: deltacycle.AggrItem
    :show-inheritance:

.. autoclass:: deltacycle.AggrValue

Tasks
=====

.. autoclass:: deltacycle.Task
    :show-inheritance:

    .. autoproperty:: coro
    .. autoproperty:: priority
    .. automethod:: state
    .. automethod:: done
    .. automethod:: cancelled
    .. automethod:: result
    .. automethod:: exception
    .. automethod:: cancel

.. autoclass:: deltacycle.TaskState

.. autoclass:: deltacycle.TaskGroup
    :show-inheritance:

    .. automethod:: deltacycle.TaskGroup.create_task

.. autofunction:: deltacycle.create_task

Synchronization Primitives
==========================

.. autoclass:: deltacycle.Event
    :show-inheritance:

    .. automethod:: deltacycle.Event.wait
    .. automethod:: deltacycle.Event.set
    .. automethod:: deltacycle.Event.clear
    .. automethod:: deltacycle.Event.is_set

.. autoclass:: deltacycle.Semaphore
    :show-inheritance:

    .. automethod:: acquire
    .. automethod:: try_acquire
    .. automethod:: release
    .. automethod:: locked

.. autoclass:: deltacycle.BoundedSemaphore
    :show-inheritance:

    .. automethod:: release

.. autoclass:: deltacycle.Lock
    :show-inheritance:

Loop
====

.. autoclass:: deltacycle.Loop

    .. automethod:: deltacycle.Loop.state
    .. automethod:: deltacycle.Loop.time
    .. autoproperty:: deltacycle.Loop.main
    .. automethod:: deltacycle.Loop.task

.. autoclass:: deltacycle.LoopState

.. autofunction:: deltacycle.get_running_loop
.. autofunction:: deltacycle.get_loop
.. autofunction:: deltacycle.set_loop

.. autofunction:: deltacycle.now

.. autofunction:: deltacycle.run
.. autofunction:: deltacycle.irun

.. autofunction:: deltacycle.finish

.. autofunction:: deltacycle.sleep

.. autofunction:: deltacycle.changed
.. autofunction:: deltacycle.touched
