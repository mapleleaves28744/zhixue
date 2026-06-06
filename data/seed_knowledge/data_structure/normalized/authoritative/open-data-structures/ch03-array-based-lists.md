---
source_id: open-data-structures
source_type: open_textbook
chapter_id: ch03
license: CC BY
source_url: https://opendatastructures.org/ods-python/
attribution: Open Data Structures (in pseudocode)
imported_at: 2026-06-06T17:44:44.451749+00:00
text_hash: d63d079390f885f2133345fcef36e2422cdf778fe15dc0869d1d0397ff40e172
---

# array based lists

2. Array-Based Lists 
Next: 2.1 ArrayStack: Fast Stack Up: Open Data Structures (in Previous: 1.8 Discussion and Exercises Contents Index 

# 2 . Array-Based Lists 

In this chapter, we will study implementations of the List and Queue
interfaces where the underlying data is stored in an array, called the backing array . The following table summarizes the running times
of operations for the data structures presented in this chapter: 

/ / 
ArrayStack 
ArrayDeque 
DualArrayDeque 
RootishArrayStack Data structures that work by storing data in a single array have many
advantages and limitations in common: 
Arrays offer constant time access to any value in the array.
  This is what allows and to run in constant time. 

Arrays are not very dynamic.  Adding or removing an element
  near the middle of a list means that a large number of elements in the
  array need to be shifted to make room for the newly added element or
  to fill in the gap created by the deleted element.  This is why the
  operations and have running times that depend
  on and . 

Arrays cannot expand or shrink.  When the number of elements in
  the data structure exceeds the size of the backing array, a new array needs
  to be allocated and the data from the old array needs to be copied
  into the new array.  This is an expensive operation. 
The third point is important.  The running times cited in the table
above do not include the cost associated with growing and shrinking
the backing array.  We will see that, if carefully managed, the cost of
growing and shrinking the backing array does not add much to the cost of
an average operation.  More precisely, if we start with an empty
data structure, and perform any sequence of or operations, then the total cost of growing and shrinking the backing
array, over the entire sequence of operations is .  Although
some individual operations are more expensive, the amortized cost,
when amortized over all operations, is only per operation. 

Subsections 
2 . 1 ArrayStack: Fast Stack Operations Using an Array 
2 . 2 FastArrayStack: An Optimized ArrayStack 
2 . 3 ArrayQueue: An Array-Based Queue 
2 . 4 ArrayDeque: Fast Deque Operations Using an Array 
2 . 5 DualArrayDeque: Building a Deque from Two Stacks 
2 . 6 RootishArrayStack: A Space-Efficient Array Stack 
2 . 7 Discussion and Exercises 
Next: 2.1 ArrayStack: Fast Stack Up: Open Data Structures (in Previous: 1.8 Discussion and Exercises Contents Index opendatastructures.org
