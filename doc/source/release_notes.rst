.. _release_notes:

#####################
    Release Notes
#####################

This chapter lists new features, API changes, and bug fixes.
For a complete history, see the Git commit log.


Version 0.10.0
==============

Added a ``Task.group`` property,
and corresponding ``get_current_task_group`` top-level function.
This will make it easier to find the active TaskGroup without having to pass it
as an argument all over the place.


Version 0.9.0
=============

Changed ``Event`` API:

* Replace ``Event.wait`` with ``Event.__await``,
* and ``Event.is_set`` with ``Event.__bool__``.

Previously::

    e = Event()
    await e.wait()
    assert e.is_set()

Now::

    e = Event()
    await e
    assert e

Lots of little updates and optimizations,
but nothing else (intentionally) visible to the user.


Version 0.8.0
=============

Got rid of ``Task.cancelled`` method.
Updated ``TaskGroup`` so it properly cancels tasks spawned by children.


Version 0.7.0
=============

Got rid of Task parent and ``qualname``.
Simplified the default task naming convention.
Added Task name to the logging filter.

Added a ``get_current_task`` function.

Simplified the Task state machine.
Got rid of pending, waiting, cancelling states.

Largest change in this release is implementation of structured concurrency
with the ``TaskGroup`` class.
Child tasks now complete out of order,
and if a child raises an exception, all siblings will be cancelled.
Multiple children may raise exceptions.
Those exceptions are collected in an ``ExceptionGroup``,
and propagated to the parent task.


Version 0.6.0
=============

Improved performance by caching task qualname,
and precomputing the legal state transitions.

Fixed a few inconsistencies with task cancellation.
Now it should behave more like ``asyncio``.

Updated logger so it tolerates not having a running loop.

Lots of documentation updates.


Version 0.5.0
=============

Updated tooling to use ``uv`` and ``ruff``.
