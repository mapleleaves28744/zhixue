---
source_id: open-data-structures
source_type: open_textbook
chapter_id: ch12
license: CC BY
source_url: https://opendatastructures.org/ods-python/
attribution: Open Data Structures (in pseudocode)
imported_at: 2026-06-06T17:44:44.505655+00:00
text_hash: 460b96b1987149db9da17e902e368f2e16db958e1bdd1588a67b21a0f0c8f681
---

# graphs

12. Graphs 
Next: 12.1 AdjacencyMatrix: Representing a Up: Open Data Structures (in Previous: 11.3 Discussion and Exercises Contents Index 

# 12 . Graphs 

In this chapter, we study two representations of graphs and basic
algorithms that use these representations. 
Mathematically, a (directed) graph is a pair where is a set of vertices and is a set of ordered pairs
of vertices called edges . An edge is directed from to ; is called the source of the edge and is called the target . A path in is a sequence of
vertices such that, for every ,
the edge is in .  A path is a cycle if, additionally, the edge is in .  A path (or
cycle) is simple if all of its vertices are unique.  If there
is a path from some vertex to some vertex then we say that is reachable from .  An example of a graph is shown
in Figure 12.1 . 

Figure 12.1: A graph with twelve vertices.  Vertices are drawn as numbered
    circles and edges are drawn as pointed curves pointing from source
    to target. 

Due to their ability to model so many phenomena, graphs have an enormous
number of applications. There are many obvious examples. Computer
networks can be modelled as graphs, with vertices corresponding to
computers and edges corresponding to (directed) communication links
between those computers.  City streets can be modelled as graphs,
with vertices representing intersections and edges representing streets
joining consecutive intersections. 
Less obvious examples occur as soon as we realize that graphs can model
any pairwise relationships within a set. For example, in a university
setting we might have a timetable conflict graph whose vertices represent
courses offered in the university and in which the edge is present
if and only if there is at least one student that is taking both class and class .  Thus, an edge indicates that the exam for class should not be scheduled at the same time as the exam for class . 
Throughout this section, we will use to denote the number of vertices
of and to denote the number of edges of .  That is, and . Furthermore, we will assume that .
Any other data that we would like to associate with the elements of can be stored in an array of length . 
Some typical operations performed on graphs are: 
: Add the edge to . 

: Remove the edge from . 

: Check if the edge 

: Return a List of all integers such that 

: Return a List of all integers such that 

Note that these operations are not terribly difficult to implement
efficiently. For example, the first three operations can be implemented
directly by using a USet, so they can be implemented in constant
expected time using the hash tables discussed in Chapter 5 .
The last two operations can be implemented in constant time by storing,
for each vertex, a list of its adjacent vertices. 
However, different applications of graphs have different performance
requirements for these operations and, ideally, we can use the simplest
implementation that satisfies all the application's requirements.
For this reason, we discuss two broad categories of graph representations. 
Subsections 
12 . 1 AdjacencyMatrix: Representing a Graph by a Matrix 
12 . 2 AdjacencyLists: A Graph as a Collection of Lists 
12 . 3 Graph Traversal 
12 . 4 Discussion and Exercises 
Next: 12.1 AdjacencyMatrix: Representing a Up: Open Data Structures (in Previous: 11.3 Discussion and Exercises Contents Index opendatastructures.org
