---
source_id: opendsa
source_type: interactive_textbook
chapter_id: ch12
license: MIT License
source_url: https://opendsa.org/
attribution: OpenDSA
imported_at: 2026-06-06T17:44:45.255297+00:00
text_hash: e5104446592c29d6eb85fa512e89ea386844703cffed72320e92cd2ee0548c89
---

# opendsa graph representations

18.1. Graphs Chapter Introduction — OpenDSA Complete Catalog 

Username Password Forgot your password? 

Register 

Username: Password Confirm Password Email: 

# OpenDSA Complete Catalog 

# Chapter 18 Graphs 

| About « 17. 3. Sequential Tree Representations :: Contents :: 18. 2. Graph Implementations » 

# 18. 1. Graphs Chapter Introduction ¶ 

# 18. 1.1. Graph Terminology and Implementation ¶ 

Graphs provide the ultimate in data structure flexibility.
A graph consists of a set of nodes, and a set of edges where an
edge connects two nodes.
Trees and lists can be viewed as special cases of graphs. 

Graphs are used to model both real-world systems and abstract
problems, and are the data structure of choice in many
applications.
Here is a small sampling of the types of problems that graphs are
routinely used for. 

Modeling connectivity in computer and communications networks. 

Representing an abstract map as a set of locations with distances
between locations. This can be used to compute shortest routes between
locations such as in a GPS routefinder. 

Modeling flow capacities in transportation networks to find which
links create the bottlenecks. 

Finding a path from a starting condition to a goal condition.
This is a common way to model problems in artificial intelligence
applications and computerized game players. 

Modeling computer algorithms, to show transitions from one program
state to another. 

Finding an acceptable order for finishing subtasks in a complex
activity, such as constructing large buildings. 

Modeling relationships such as family trees, business or military
organizations, and scientific taxonomies. 

The rest of this module covers some basic graph terminology.
The following modules will describe fundamental representations for
graphs, provide a reference implementation, and cover
core graph algorithms including traversal, topological sort, shortest
paths algorithms, and algorithms to find the minimal-cost spanning tree.
Besides being useful and interesting in their own right, these
algorithms illustrate the use of many other data structures presented
throughout the course. 

A graph \(\mathbf{G} = (\mathbf{V}, \mathbf{E})\) consists
of a set of vertices \(\mathbf{V}\) and a set of edges \(\mathbf{E}\) ,
such that each edge in \(\mathbf{E}\) is a connection between a
pair of vertices in \(\mathbf{V}\) . [ 1 ] The number of vertices is written \(|\mathbf{V}|\) , and the number
of edges is written \(|\mathbf{E}|\) . \(|\mathbf{E}|\) can range from zero to a maximum of \(|\mathbf{V}|^2 - |\mathbf{V}|\) . 
[ 1 ] 
Some graph applications require that a given pair of vertices
can have multiple or parallel edges connecting them, or that a
vertex can have an edge to itself.
However, the applications discussed here do not require
either of these special cases.
To simplify our graph API, we will assume that there are no
dupicate edges, and no edges that connect a node to itself. 

A graph whose edges are not directed is called an undirected graph , as shown in part (a) of the following figure.
A graph with edges directed from one vertex to another
(as in (b)) is called a directed graph or digraph .
A graph with labels associated with its vertices
(as in (c)) is called a labeled graph .
Associated with each edge may be a cost or weight .
A graph whose edges have weights
(as in (c)) is said to be a weighted graph . 

Figure 18.1.1: Some types of graphs. 

An edge connecting Vertices \(a\) and \(b\) is written \((a, b)\) .
Such an edge is said to be incident with Vertices \(a\) and \(b\) .
The two vertices are said to be adjacent .
If the edge is directed from \(a\) to \(b\) ,
then we say that \(a\) is adjacent to \(b\) ,
and \(b\) is adjacent from \(a\) .
The degree of a vertex is the number of edges it is incident
with.
For example, Vertex \(e\) below has a degree of three. 

In a directed graph, the out degree for a vertex is the number
of neighbors adjacent from it (or the number of edges going out from
it), while the in degree is the number of neighbors adjacent
to it (or the number of edges coming in to it).
In (c) above, the in degree of Vertex 1 is two,
and its out degree is one. 

A sequence of vertices \(v_1, v_2, ..., v_n\) forms a path of length \(n-1\) if there exist edges from \(v_i\) to \(v_{i+1}\) for \(1 \leq i < n\) .
A path is a simple path if all vertices on the path are
distinct.
The length of a path is the number of edges it contains.
A cycle is a path of length three or more that connects
some vertex \(v_1\) to itself.
A cycle is a simple cycle if the path is simple, except for
the first and last vertices being the same. 

An undirected graph is a connected graph if there is at least
one path from any vertex to any other.
The maximally connected subgraphs of an undirected graph are called connected components .
For example, this figure shows an undirected graph
with three connected components. 

A graph with relatively few edges is called a sparse graph ,
while a graph with many edges is called a dense graph .
A graph containing all possible edges is said to be a complete graph .
A subgraph \(\mathbf{S}\) is formed from graph \(\mathbf{G}\) by selecting a subset \(\mathbf{V}_s\) of \(\mathbf{G}\) ’s vertices and a subset \(\mathbf{E}_s\) of \(\mathbf{G}\) ‘s edges such that for every
edge \(e  \in \mathbf{E}_s\) ,
both vertices of \(e\) are in \(\mathbf{V}_s\) .
Any subgraph of \(V\) where all vertices in the graph connect to
all other vertices in the subgraph is called a clique . 

A graph without cycles is called an acyclic graph .
Thus, a directed graph without cycles is called a directed acyclic graph or DAG . 

A free tree is a connected, undirected graph with no simple
cycles.
An equivalent definition is that
a free tree is connected and has \(|\mathbf{V}| - 1\) edges. 

# 18. 1.1.1. Graph Representations ¶ 

There are two commonly used methods for representing graphs.
The adjacency matrix for a graph is a \(|\mathbf{V}| \times |\mathbf{V}|\) array.
We typically label the vertices from \(v_0\) through \(v_{|\mathbf{V}|-1}\) .
Row \(i\) of the adjacency matrix contains entries for
Vertex \(v_i\) .
Column \(j\) in row \(i\) is marked if there is an edge
from \(v_i\) to \(v_j\) and is not marked otherwise.
The space requirements for the adjacency matrix are \(\Theta(|\mathbf{V}|^2)\) . 

The second common representation for graphs is the adjacency list .
The adjacency list is an array of linked lists.
The array is \(|\mathbf{V}|\) items long, with position \(i\) storing a pointer to the linked list of edges for Vertex \(v_i\) .
This linked list represents the edges by the vertices that are
adjacent to Vertex \(v_i\) . 

Here is an example of the two representations on a directed graph.
The entry for Vertex 0 stores 1 and 4 because there are two edges
in the graph leaving Vertex 0, with one going to Vertex 1 and one
going to Vertex 4.
The list for Vertex 2 stores an entry for Vertex 4 because there is
an edge from Vertex 2 to Vertex 4, but no entry for Vertex 3
because this edge comes into Vertex 2 rather than going out. 

Figure 18.1.7: Representing a directed graph. 

Both the adjacency matrix and the adjacency list can be used to store
directed or undirected graphs.
Each edge of an undirected graph connecting Vertices \(u\) and \(v\) is represented by two directed edges: one from \(u\) to \(v\) and one from \(v\) to \(u\) .
Here is an example of the two representations on an undirected graph.
We see that there are twice as many edge entries in both the adjacency
matrix and the adjacency list.
For example, for the undirected graph, the list for Vertex 2 stores an
entry for both Vertex 3 and Vertex 4. 

Figure 18.1.8: Representing an undirected graph. 

The storage requirements for the adjacency list depend on both the
number of edges and the number of vertices in the graph.
There must be an array entry for each vertex (even if the vertex is
not adjacent to any other vertex and thus has no elements on its
linked list), and each edge must appear on one of the lists.
Thus, the cost is \(\Theta(|\mathbf{V}| + |\mathbf{E}|)\) . 

Sometimes we want to store weights or distances with each each edge,
such as in Figure 18.1.1 (c).
This is easy with the adjacency matrix, where we will just store
values for the weights in the matrix.
In Figures 18.1.7 and 18.1.8 we
store a value of “1” at each position just to show that the edge
exists.
That could have been done using a single bit, but since bit
manipulation is typically complicated in most programming languages,
an implementation might store a byte or an integer at each matrix
position.
For a weighted graph, we would need to store at each position in the
matrix enough space to represent the weight, which might typically be
an integer. 

The adjacency list needs to explicitly store a weight with each edge.
In the adjacency list shown below, each linked list node is shown
storing two values.
The first is the index for the neighbor at the end of the associated
edge.
The second is the value for the weight.
As with the adjacency matrix, this value requires space to represent,
typically an integer. 

Which graph representation is more space efficient depends on the
number of edges in the graph.
The adjacency list stores information only for those edges that
actually appear in the graph, while the adjacency matrix requires
space for each potential edge, whether it exists or not.
However, the adjacency matrix requires no overhead for pointers,
which can be a substantial cost, especially if the only information
stored for an edge is one bit to indicate its existence.
As the graph becomes denser, the adjacency matrix becomes
relatively more space efficient.
Sparse graphs are likely to have their adjacency list representation
be more space efficient. 

Example 18.1.1 

Assume that a vertex index requires two bytes, a pointer requires
four bytes, and an edge weight requires two bytes.
Then, each link node in the adjacency list needs \(2 + 2 + 4 = 8\) bytes.
The adjacency matrix for the directed graph above
requires \(2 |\mathbf{V}^2| = 50\) bytes while the adjacency list
requires \(4 |\mathbf{V}| + 8 |\mathbf{E}| = 68\) bytes.
For the undirected version of the graph above, the adjacency
matrix requires the same space as before, while the adjacency list
requires \(4 |\mathbf{V}| + 8 |\mathbf{E}| = 116\) bytes
(because there are now 12 edges represented instead of 6). 

The adjacency matrix often requires a higher asymptotic cost for an
algorithm than would result if the adjacency list were used.
The reason is that it is common for a graph algorithm
to visit each neighbor of each vertex.
Using the adjacency list, only the actual edges connecting a vertex to
its neighbors are examined.
However, the adjacency matrix must look at each of its \(|\mathbf{V}|\) potential edges, yielding a total cost of \(\Theta(|\mathbf{V}^2|)\) time when the algorithm might otherwise require only \(\Theta(|\mathbf{V}| + |\mathbf{E}|)\) time.
This is a considerable disadvantage when the graph is sparse,
but not when the graph is closer to full. 

# 18. 1.2. Graph Terminology Questions ¶ 

Contact Us | | Privacy | | License « 17. 3. Sequential Tree Representations :: Contents :: 18. 2. Graph Implementations » 

Contact Us | | Report a bug 
© Copyright 2011-2025 by OpenDSA Project Contributors and distributed under an MIT license.
      Last updated on May 02, 2025.
      Created using Sphinx 5.2.1. 

Summary*: Operating system*: Windows Mac OS Linux iOS Android Other Browser*: Chrome Safari Internet Explorer Opera Other Description*: Attach a screenshot (optional):
