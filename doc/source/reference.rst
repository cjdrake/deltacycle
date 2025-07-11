.. _reference:

#################
    Reference
#################


Variables
=========

.. autoclass:: deltacycle.Variable
    :show-inheritance:

    .. automethod:: __await__
    .. automethod:: changed
    .. automethod:: update

.. autoclass:: deltacycle.Value
    :show-inheritance:

    .. automethod:: get_prev
    .. autoproperty:: prev
    .. automethod:: set_next
    .. autoproperty:: next

.. autoclass:: deltacycle.Singular
    :show-inheritance:

    .. automethod:: get_value
    .. autoproperty:: value

.. autoclass:: deltacycle.Aggregate
    :show-inheritance:

    .. automethod:: __getitem__
    .. automethod:: get_prev
    .. automethod:: set_next
    .. automethod:: get_value
    .. autoproperty:: value

.. autoclass:: deltacycle.AggrItem
    :show-inheritance:

.. autoclass:: deltacycle.AggrValue

    .. automethod:: __getitem__

.. autofunction:: deltacycle.any_var


Tasks
=====

.. autoexception:: deltacycle.Signal

.. autoexception:: deltacycle.Interrupt
    :show-inheritance:

.. autoclass:: deltacycle.Task.State

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
    .. automethod:: interrupt

.. autoclass:: deltacycle.TaskGroup
    :show-inheritance:

    .. automethod:: __aenter__
    .. automethod:: __aexit__
    .. automethod:: create_task

.. autofunction:: deltacycle.create_task
.. autofunction:: deltacycle.get_current_task


Synchronization Primitives
==========================

.. autoclass:: deltacycle.Event
    :show-inheritance:

    .. automethod:: __bool__
    .. automethod:: __await__
    .. automethod:: set
    .. automethod:: clear

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


Kernel
======

.. autoclass:: deltacycle.Kernel.State

.. autoclass:: deltacycle.Kernel

    .. automethod:: state
    .. automethod:: time
    .. autoproperty:: main
    .. automethod:: task
    .. automethod:: done

.. autofunction:: deltacycle.finish

.. autofunction:: deltacycle.get_running_kernel
.. autofunction:: deltacycle.get_kernel
.. autofunction:: deltacycle.set_kernel

.. autofunction:: deltacycle.run
.. autofunction:: deltacycle.step

.. autofunction:: deltacycle.now
.. autofunction:: deltacycle.sleep
