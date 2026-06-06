---
source_id: runestone-pythonds
source_type: open_textbook
chapter_id: ch12
license: CC BY-NC-SA 4.0
source_url: https://runestone.academy/ns/books/published/pythonds/index.html
attribution: Problem Solving with Algorithms and Data Structures using Python
imported_at: 2026-06-06T17:44:44.727702+00:00
text_hash: b31464763b509d1a749579ed8dbffa3f5f8d7f43ef1cad0136016e7560ce3f52
---

# an adjacency list

..  Copyright (C)  Brad Miller, David Ranum
    This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.

An Adjacency List
~~~~~~~~~~~~~~~~~

A more space-efficient way to implement a sparsely connected graph is to
use an adjacency list. In an adjacency list implementation, we keep a
master list of all the vertices in the ``Graph`` object, and each vertex
object in the graph maintains a list of the other vertices that it is
connected to. In our implementation of the ``Vertex`` class we will use
a dictionary rather than a list, where the dictionary keys are the
vertices and the values are the weights. :ref:`Figure 4 <fig_adjlist>`
illustrates the adjacency list representation for the graph in
:ref:`Figure 2 <fig_dgsimple>`.

.. _fig_adjlist:

.. figure:: Figures/adjlist.png
   :align: center

   Figure 4: An Adjacency List Representation of a Graph

The advantage of the adjacency list implementation is that it allows us
to compactly represent a sparse graph. The adjacency list also allows us
to easily find all the links that are directly connected to a particular
vertex.
