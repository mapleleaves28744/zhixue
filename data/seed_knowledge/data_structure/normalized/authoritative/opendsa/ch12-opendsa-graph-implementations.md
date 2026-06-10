---
source_id: opendsa
source_type: interactive_textbook
chapter_id: ch12
license: MIT License
source_url: https://opendsa.org/
attribution: OpenDSA
imported_at: 2026-06-06T17:44:45.139536+00:00
text_hash: 66913c5b95549b5dad0320d442eba0ed7708bccf4096c18a76f68cd6cb7f3c1d
---

# opendsa graph implementations

18.2. Graph Implementations — OpenDSA Complete Catalog 

Username Password Forgot your password? 

Register 

Username: Password Confirm Password Email: 

# OpenDSA Complete Catalog 

# Chapter 18 Graphs 

| About « 18. 1. Graphs Chapter Introduction :: Contents :: 18. 3. Graph Traversals » 

# 18. 2. Graph Implementations ¶ 

We next turn to the problem of implementing a general-purpose graph class.
There are two traditional approaches to representing graphs:
The adjacency matrix and the adjacency list .
In this module we will show actual implementations for each approach.
We will begin with an interface defining an ADT for graphs that a
given implementation must meet. 

interface Graph { // Graph class ADT // Initialize the graph with some number of vertices void init ( int n ); // Return the number of vertices int nodeCount (); // Return the current number of edges int edgeCount (); // Get the value of node with index v Object getValue ( int v ); // Set the value of node with index v void setValue ( int v , Object val ); // Adds a new edge from node v to node w with weight wgt void addEdge ( int v , int w , int wgt ); // Get the weight value for an edge int weight ( int v , int w ); // Removes the edge from the graph. void removeEdge ( int v , int w ); // Returns true iff the graph has the edge boolean hasEdge ( int v , int w ); // Returns an array containing the indicies of the neighbors of v int [] neighbors ( int v ); } 

This ADT assumes that the number of vertices is fixed
when the graph is created, but that edges can be added and removed.
The init method sets (or resets) the number of nodes in the graph,
and creates necessary space for the adjacency matrix or adjacency list. 

Vertices are defined by an integer index value.
In other words, there is a Vertex 0, Vertex 1, and so on through
Vertex \(n-1\) .
We can assume that the graph’s client application stores any additional
information of interest about a given vertex elsewhere, such as a name
or application-dependent value.
Note that in a language like Java or C++, this ADT would not be
implemented using a language feature like a generic or template,
because it is the Graph class users’ responsibility to maintain
information related to the vertices themselves.
The Graph class need have no knowledge of the type or content
of the information associated with a vertex, only the index number for
that vertex. 

Interface Graph has methods to return the number of vertices and
edges (methods n and e , respectively).
Function weight returns the weight of a given edge, with that
edge identified by its two incident vertices.
For example, calling weight(0, 4) on the graph of
Figure 18.1.1 (c) would return 4.
If no such edge exists, the weight is defined to be 0.
So calling weight(0, 2) on the graph of
Figure 18.1.1 (c) would return 0. 

Functions addEdge and removeEdge add an edge (setting its
weight) and removes an edge from the graph, respectively.
Again, an edge is identified by its two incident vertices. addEdge does not permit the user to set the weight to be 0,
because this value is used to indicate a non-existent edge, nor are
negative edge weights permitted.
Functions getValue and setValue get and set, respectively,
a requested value for Vertex \(v\) .
In our example applications the most frequent use of these methods
will be to indicate whether a given node has previously been visited
in the process of the algorithm 

Nearly every graph algorithm presented in this chapter will require
visits to all neighbors of a given vertex.
The neighbors method returns an array containing the indices for
the neighboring vertices, in ascending order.
The following lines appear in many graph algorithms. 

int [] nList = G . neighbors ( v ); for ( int i = 0 ; i < nList . length ; i ++ ) { if ( G . getValue ( nList [ i ] ) != VISITED ) { DoSomething (); } } 

First, an array is generated that contains the indices of the nodes
that can be directly reached from node v .
The for loop then iterates through this neighbor array to execute
some function on each. 

It is reasonably straightforward to implement our graph ADT
using either the adjacency list or adjacency matrix.
The sample implementations presented here do not address the issue of
how the graph is actually created.
The user of these implementations must add functionality for
this purpose, perhaps reading the graph description from a file.
The graph can be built up by using the addEdge function
provided by the ADT. 

Here is an implementation for the adjacency matrix. 

class GraphM implements Graph { private int [][] matrix ; private Object [] nodeValues ; private int numEdge ; // No real constructor needed GraphM () { } // Initialize the graph with n vertices public void init ( int n ) { matrix = new int [ n ][ n ] ; nodeValues = new Object [ n ] ; numEdge = 0 ; } // Return the number of vertices public int nodeCount () { return nodeValues . length ; } // Return the current number of edges public int edgeCount () { return numEdge ; } // Get the value of node with index v public Object getValue ( int v ) { return nodeValues [ v ] ; } // Set the value of node with index v public void setValue ( int v , Object val ) { nodeValues [ v ] = val ; } // Adds a new edge from node v to node w // Returns the new edge public void addEdge ( int v , int w , int wgt ) { if ( wgt == 0 ) { return ; } // Can't store weight of 0 if ( matrix [ v ][ w ] == 0 ) { numEdge ++ ; } matrix [ v ][ w ] = wgt ; } // Get the weight value for an edge public int weight ( int v , int w ) { return matrix [ v ][ w ] ; } // Removes the edge from the graph. public void removeEdge ( int v , int w ) { if ( matrix [ v ][ w ] != 0 ) { matrix [ v ][ w ] = 0 ; numEdge -- ; } } // Returns true iff the graph has the edge public boolean hasEdge ( int v , int w ) { return matrix [ v ][ w ] != 0 ; } // Returns an array containing the indicies of the neighbors of v public int [] neighbors ( int v ) { int i ; int count = 0 ; int [] temp ; for ( i = 0 ; i < nodeValues . length ; i ++ ) { if ( matrix [ v ][ i ] != 0 ) { count ++ ; } } temp = new int [ count ] ; for ( i = 0 , count = 0 ; i < nodeValues . length ; i ++ ) { if ( matrix [ v ][ i ] != 0 ) { temp [ count ++] = i ; } } return temp ; } } 

Array nodeValues stores the information manipulated by the setValue and getValue functions.
The edge matrix is implemented as an integer array of size \(n \times n\) for a graph of \(n\) vertices.
Position \((i, j)\) in the matrix stores the weight for edge \((i, j)\) if it exists.
A weight of zero for edge \((i, j)\) is used to indicate that no
edge connects Vertices \(i\) and \(j\) . 

Given a vertex \(v\) , the neighbors method scans through row v of the matix to locate the positions of the various neighbors.
If no edge is incident on \(v\) , then returned neighbor array will
have length 0.
Functions addEdge and removeEdge adjust the
appropriate value in the array.
Function weight returns the value stored in the
appropriate position in the array. 

Here is an implementation of the adjacency list representation for
graphs.
Its main data structure is an array of linked lists, one linked list
for each vertex.
These linked lists store objects of type Edge , which merely
stores the index for the vertex pointed to by the edge, along with the
weight of the edge. 

public class GraphL implements Graph { private class Edge { // Doubly linked list node int vertex , weight ; Edge prev , next ; Edge ( int v , int w , Edge p , Edge n ) { vertex = v ; weight = w ; prev = p ; next = n ; } } private Edge [] nodeArray ; private Object [] nodeValues ; private int numEdge ; // No real constructor needed GraphL () {} // Initialize the graph with n vertices public void init ( int n ) { nodeArray = new Edge [ n ] ; // List headers; for ( int i = 0 ; i < n ; i ++ ) { nodeArray [ i ] = new Edge ( - 1 , - 1 , null , null ); } nodeValues = new Object [ n ] ; numEdge = 0 ; } // Return the number of vertices public int nodeCount () { return nodeArray . length ; } // Return the current number of edges public int edgeCount () { return numEdge ; } // Get the value of node with index v public Object getValue ( int v ) { return nodeValues [ v ] ; } // Set the value of node with index v public void setValue ( int v , Object val ) { nodeValues [ v ] = val ; } // Return the link in v's neighbor list that preceeds the // one with w (or where it would be) private Edge find ( int v , int w ) { Edge curr = nodeArray [ v ] ; while (( curr . next != null ) && ( curr . next . vertex < w )) { curr = curr . next ; } return curr ; } // Adds a new edge from node v to node w with weight wgt public void addEdge ( int v , int w , int wgt ) { if ( wgt == 0 ) { return ; } // Can't store weight of 0 Edge curr = find ( v , w ); if (( curr . next != null ) && ( curr . next . vertex == w )) { curr . next . weight = wgt ; } else { curr . next = new Edge ( w , wgt , curr , curr . next ); numEdge ++ ; if ( curr . next . next != null ) { curr . next . next . prev = curr . next ; } } } // Get the weight value for an edge public int weight ( int v , int w ) { Edge curr = find ( v , w ); if (( curr . next == null ) || ( curr . next . vertex != w )) { return 0 ; } else { return curr . next . weight ; } } // Removes the edge from the graph. public void removeEdge ( int v , int w ) { Edge curr = find ( v , w ); if (( curr . next == null ) || curr . next . vertex != w ) { return ; } else { curr . next = curr . next . next ; if ( curr . next != null ) { curr . next . prev = curr ; } } numEdge -- ; } // Returns true iff the graph has the edge public boolean hasEdge ( int v , int w ) { return weight ( v , w ) != 0 ; } // Returns an array containing the indicies of the neighbors of v public int [] neighbors ( int v ) { int cnt = 0 ; Edge curr ; for ( curr = nodeArray [ v ] . next ; curr != null ; curr = curr . next ) { cnt ++ ; } int [] temp = new int [ cnt ] ; cnt = 0 ; for ( curr = nodeArray [ v ] . next ; curr != null ; curr = curr . next ) { temp [ cnt ++] = curr . vertex ; } return temp ; } } 

Implementation for GraphL member functions is straightforward
in principle, with the key functions being addEdge , removeEdge , and weight .
They simply start at the beginning of the adjacency list and move
along it until the desired vertex has been found.
Private method find is a utility for finding the last edge preceding
the one that holds vertex \(v\) if that exists. 

Contact Us | | Privacy | | License « 18. 1. Graphs Chapter Introduction :: Contents :: 18. 3. Graph Traversals » 

Contact Us | | Report a bug 
© Copyright 2011-2025 by OpenDSA Project Contributors and distributed under an MIT license.
      Last updated on May 02, 2025.
      Created using Sphinx 5.2.1. 

Summary*: Operating system*: Windows Mac OS Linux iOS Android Other Browser*: Chrome Safari Internet Explorer Opera Other Description*: Attach a screenshot (optional):
