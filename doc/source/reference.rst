.. _reference:

#################
    Reference
#################


Variables
=========

.. autoclass:: deltacycle.Variable
    :show-inheritance:

    .. automethod:: __await__
    .. automethod:: pred
    .. automethod:: changed
    .. automethod:: update

.. autoclass:: deltacycle.PredVar

    .. automethod:: __await__

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


Tasks
=====

.. autotype:: deltacycle.TaskCoro

.. autoexception:: deltacycle.Throwable

.. autoexception:: deltacycle.Interrupt
    :show-inheritance:

.. autoclass:: deltacycle.Task.State

.. autoclass:: deltacycle.Task
    :show-inheritance:

    .. automethod:: __await__
    .. autoproperty:: coro
    .. autoproperty:: name
    .. autoproperty:: group
    .. automethod:: state
    .. automethod:: done
    .. automethod:: result
    .. automethod:: exception
    .. automethod:: interrupt

.. autoclass:: deltacycle.TaskQueue

    .. automethod:: __bool__
    .. automethod:: push
    .. automethod:: pop
    .. automethod:: drop

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

    .. automethod:: __await__
    .. automethod:: __bool__
    .. automethod:: set
    .. automethod:: clear

.. autoclass:: deltacycle.Semaphore
    :show-inheritance:

    .. automethod:: __len__
    .. autoproperty:: capacity
    .. automethod:: req
    .. automethod:: put
    .. automethod:: try_get
    .. automethod:: get

.. autoclass:: deltacycle.ReqSemaphore

    .. automethod:: __aenter__
    .. automethod:: __aexit__

.. autoclass:: deltacycle.Lock
    :show-inheritance:

.. autoclass:: deltacycle.CreditPool
    :show-inheritance:

    .. automethod:: __len__
    .. autoproperty:: capacity
    .. automethod:: req
    .. automethod:: put
    .. automethod:: try_get
    .. automethod:: get

.. autoclass:: deltacycle.ReqCredit

    .. automethod:: __aenter__
    .. automethod:: __aexit__


Scheduling
==========

.. autoclass:: deltacycle.Blocking
.. autoclass:: deltacycle.Sendable

.. autoclass:: deltacycle.AllOf
.. autoclass:: deltacycle.AnyOf


Queues
======

.. autoclass:: deltacycle.Queue
    :show-inheritance:

    .. automethod:: __len__
    .. autoproperty:: capacity
    .. automethod:: empty
    .. automethod:: full
    .. automethod:: try_put
    .. automethod:: put
    .. automethod:: try_get
    .. automethod:: get


Container
=========

.. autoclass:: deltacycle.Container
    :show-inheritance:

    .. automethod:: __len__
    .. autoproperty:: capacity
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
    .. automethod:: clear
    .. automethod:: call_soon
    .. automethod:: call_later
    .. automethod:: call_at
    .. automethod:: create_main
    .. automethod:: create_task

.. autoclass:: deltacycle.DefaultKernel

.. autofunction:: deltacycle.finish

.. autofunction:: deltacycle.get_running_kernel
.. autofunction:: deltacycle.get_kernel
.. autofunction:: deltacycle.set_kernel

.. autofunction:: deltacycle.run
.. autofunction:: deltacycle.step

.. autofunction:: deltacycle.now
.. autofunction:: deltacycle.sleep

.. autofunction:: deltacycle.all_of
.. autofunction:: deltacycle.any_of
