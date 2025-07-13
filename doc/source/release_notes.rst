.. _release_notes:

#####################
    Release Notes
#####################

This chapter lists new features, API changes, and bug fixes.
For a complete history, see the Git commit log.


Version 0.18.0
==============

* Renamed ``irun`` function to ``step``.
* Got rid of both ``any_event`` and ``any_var`` public functions.
  Replaced by ``Schedule`` class.

Also, unfortunately had to get rid of ``e1 | e2 | ...`` syntax.
It might be fine for tasks and events, but we need to reserve the ``|``
operator for variable operator overloading.
Use ``Schedule(t1, e1, v1, ...)`` to mix and match task/event/variable
"schedule" items.

Lots of refactoring this release.
Probably forgot to mention a few things.


Version 0.17.0
==============

* Renamed slightly ambiguous ``Loop`` (or "event loop") to ``Kernel``.


Version 0.16.0
==============

* Moved ``LoopState`` class into ``Loop``, now called ``Loop.State``.
* Moved ``TaskState`` class into ``Task``, now called ``Task.State``.


Version 0.15.0
==============

* Renamed ``TaskState.RESULTED`` to ``TaskState.RETURNED``.
* Added a ``TaskState.PENDING`` state.
* Renamed ``Task.cancel`` to ``Task.interrupt``.
* ``TaskGroup`` children are now killed instead of cancelled/interrupted.
* Added a new ``Signal`` base class for ``Interrupt`` and ``_Kill`` (undocumented).


Version 0.14.0
==============

Renamed ``InvalidStateError`` to ``TaskStateError``.
Otherwise, mostly type cleanup.


Version 0.13.0
==============

Added an ``EventList`` class,
to enable waiting for the first event to fire using ``e1 | e2 | ...`` syntax.

For example::

    # Previously
    >>> e = any_event(e1, e2, ...)
    # New syntax
    >>> e = await (e0 | e1 | ...)


Version 0.12.0
==============

Change a few ``Variable`` method names from ``_protected`` to public:

* ``_get_prev`` => ``get_prev``
* ``_set_next`` => ``set_next``
* ``_get_value`` => ``get_value``
* ``_get_next`` => ``get_next``


Version 0.11.0
==============

* Got rid of ``Loop.finished`` method.
* Got rid of ``changed`` function.
* Added new ``any_event(e1, e2, ...)`` function.
* Renamed ``touched`` to ``any_var``.


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
