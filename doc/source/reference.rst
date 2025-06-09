.. _reference:

#################
    Reference
#################


Variables
=========

.. autoclass:: deltacycle.Variable
    :show-inheritance:

    .. autoproperty:: value
    .. automethod:: __await__
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

.. autoexception:: deltacycle.CancelledError
.. autoexception:: deltacycle.InvalidStateError

.. autoclass:: deltacycle.TaskState

.. autoclass:: deltacycle.Task
    :show-inheritance:

    .. automethod:: __await__
    .. autoproperty:: coro
    .. autoproperty:: name
    .. autoproperty:: priority
    .. autoproperty:: group
    .. automethod:: state
    .. automethod:: done
    .. automethod:: result
    .. automethod:: exception
    .. automethod:: cancel

.. autoclass:: deltacycle.TaskGroup
    :show-inheritance:

    .. automethod:: deltacycle.TaskGroup.create_task

.. autofunction:: deltacycle.create_task


Synchronization Primitives
==========================

.. autoclass:: deltacycle.Event
    :show-inheritance:

    .. automethod:: deltacycle.Event.__bool__
    .. automethod:: deltacycle.Event.__await__
    .. automethod:: deltacycle.Event.set
    .. automethod:: deltacycle.Event.clear

.. autoclass:: deltacycle.Semaphore
    :show-inheritance:

    .. automethod:: put
    .. automethod:: try_get
    .. automethod:: get

.. autoclass:: deltacycle.BoundedSemaphore
    :show-inheritance:

    .. automethod:: put

.. autoclass:: deltacycle.Lock
    :show-inheritance:


Queues
======

.. autoclass:: deltacycle.Queue
    :show-inheritance:

    .. automethod:: empty
    .. automethod:: full
    .. automethod:: try_put
    .. automethod:: put
    .. automethod:: try_get
    .. automethod:: get


Loop
====

.. autoclass:: deltacycle.LoopState

.. autoclass:: deltacycle.Loop

    .. automethod:: deltacycle.Loop.state
    .. automethod:: deltacycle.Loop.time
    .. autoproperty:: deltacycle.Loop.main
    .. automethod:: deltacycle.Loop.task
    .. automethod:: deltacycle.Loop.done
    .. automethod:: deltacycle.Loop.finished

.. autofunction:: deltacycle.get_running_loop
.. autofunction:: deltacycle.get_current_task
.. autofunction:: deltacycle.get_current_task_group
.. autofunction:: deltacycle.get_loop
.. autofunction:: deltacycle.set_loop

.. autofunction:: deltacycle.now

.. autofunction:: deltacycle.run
.. autofunction:: deltacycle.irun

.. autofunction:: deltacycle.finish

.. autofunction:: deltacycle.sleep

.. autofunction:: deltacycle.changed
.. autofunction:: deltacycle.touched
