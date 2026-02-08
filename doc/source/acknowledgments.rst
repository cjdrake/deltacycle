.. _acknowledgments:

########################
    Acknowledgments
########################

DeltaCycle was originally created as the "sim" module of the `seqlogic`_
experimental Meta-HDL project.
The author has since extracted it into a separate library.
The first version is `here <https://github.com/cjdrake/seqlogic/commit/bf9a28329371fa01680fd114fbf6310d953cf26b>`_.
Original features were geared towards hardware design and verification.

The inspiration for using Python's ``async`` / ``await`` syntax came from
David Beazley's
`Build Your Own Async <https://www.youtube.com/watch?v=Y4Gt3Xjd7G8>`_ tutorial.
The talk "focuses on the core problem of implementing concurrency in lieu of threads",
which comes in handy when implementing concurrency in Python.

The implementation of structured concurrency follows concepts from
Nathaniel J. Smith's blog post
`Notes on structured concurrency, or: Go statement considered harmful <https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful>`_.

The IEEE `SystemVerilog`_ standard is *significantly* more complicated than DeltaCycle.
However, we have adapted names and ideas from sections 4.3 "Event Simulation",
and 6.4 "Singular and Aggregate Types".

Some API names and conventions were adapted from the following libraries:

* `asyncio`_ by Python Software Foundation
* `SimPy`_ by Team SimPy

Finally, I want to thank Nathan Binkert.
He and I were both part of the Advanced Computer Architecture Lab (ACAL)
at University of Michigan's EECS graduate school, circa 2005.
We lived in the same apartment complex in Ann Arbor near North Campus,
and occasionally participated in triathlons together.
When I was getting ready to leave with my MSE degree,
he was nearing completion of his PhD thesis:
`Integration System Architecture for High-Performance Internet Servers <https://backend.production.deepblue-documents.lib.umich.edu/server/api/core/bitstreams/99d0dacf-a520-48c7-81fc-f01c1cc214f9/content>`_.
The title of Chapter 3 is "Network Simulation with the M5 Simulator".
I once asked Nate for advice about research topics.
As God is my witness, he told me "never write a simulator".
The irony is that Nate was the lead developer of M5 and `gem5 <https://www.gem5.org>`_,
two highly influential simulators in the field of computer architecture research.
Tragically, Nate died in 2017.
It took me a while, but I finally got around to defying his advice 🙂.


.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _seqlogic: https://github.com/cjdrake/seqlogic
.. _SimPy: https://simpy.rtfd.org
.. _SystemVerilog: https://standards.ieee.org/ieee/1800/7743
