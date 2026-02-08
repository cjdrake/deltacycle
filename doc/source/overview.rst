.. _overview:

################
    Overview
################

DeltaCycle is a Python library for discrete event simulation (DES).
Using the intuitive `async / await <https://peps.python.org/pep-0492/>`_ syntax,
it provides a natural language for modeling complex systems to solve real-world problems.

To appropriate a familiar aphorism, it's DES for humans.

A simulation has two components:

* a collection of *variables*
* a collection of *tasks*

Variables represent the instantaneous state of the simulation.
They may be organized into arbitrary data structures.

Tasks define how the simulation state evolves.
They may appear concurrent, but are scheduled sequentially.

DeltaCycle's simulation kernel was designed to support a range of scheduling semantics,
from the fine-grained inter-timeslot "delta cycle" ordering of digital logic events,
to the relatively coarse-grained requirements of industrial engineering and operations research.
