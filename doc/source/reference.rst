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
.. autoclass:: deltacycle.Value
.. autoclass:: deltacycle.Singular
.. autoclass:: deltacycle.Aggregate
.. autoclass:: deltacycle.AggrItem
.. autoclass:: deltacycle.AggrValue

Tasks
=====

.. autoclass:: deltacycle.Task
.. autoclass:: deltacycle.TaskState
.. autoclass:: deltacycle.TaskGroup

.. autofunction:: deltacycle.create_task

Synchronization Primitives
==========================

.. autoclass:: deltacycle.Event
.. autoclass:: deltacycle.Semaphore
.. autoclass:: deltacycle.BoundedSemaphore
.. autoclass:: deltacycle.Lock

Loop
====

.. autoclass:: deltacycle.Loop
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
