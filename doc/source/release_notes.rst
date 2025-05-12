.. _release_notes:

#####################
    Release Notes
#####################

This chapter lists new features, API changes, and bug fixes.
For a complete history, see the Git commit log.


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
