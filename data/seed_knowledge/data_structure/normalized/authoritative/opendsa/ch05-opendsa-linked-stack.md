---
source_id: opendsa
source_type: interactive_textbook
chapter_id: ch05
license: MIT License
source_url: https://opendsa.org/
attribution: OpenDSA
imported_at: 2026-06-06T17:44:45.560071+00:00
text_hash: 7f1317132408b33cff3d4db6b8f30e83936cd37677fcdca49f0de724f1233584
---

# opendsa linked stack

9.9. Linked Stacks — OpenDSA Data Structures and Algorithms Modules Collection 

# OpenDSA Data Structures and Algorithms Modules Collection 

# Chapter 9 Linear Structures 

| About « 9. 8. Stacks :: Contents :: 9. 10. Freelists » 

# 9. 9. Linked Stacks ¶ 

# 9. 9.1. Linked Stack Implementation ¶ 

The linked stack implementation is quite simple.
Elements are inserted and removed only from the head of the list.
A header node is not used because no special-case code is required
for lists of zero or one elements.
Here is the complete linked stack implementation. 

Java 

Java (Generic) 

// Linked stack implementation class LStack implements Stack { private Link top ; // Pointer to first element private int size ; // Number of elements // Constructors LStack () { top = null ; size = 0 ; } LStack ( int size ) { top = null ; size = 0 ; } // Reinitialize stack public void clear () { top = null ; size = 0 ; } // Put "it" on stack public boolean push ( Object it ) { top = new Link ( it , top ); size ++ ; return true ; } // Remove "it" from stack public Object pop () { if ( top == null ) return null ; Object it = top . element (); top = top . next (); size -- ; return it ; } public Object topValue () { // Return top value if ( top == null ) return null ; return top . element (); } // Return stack length public int length () { return size ; } // Check if the stack is empty public boolean isEmpty () { return size == 0 ; } } 

// Linked stack implementation class LStack < E > implements Stack < E > { private Link < E > top ; // Pointer to first element private int size ; // Number of elements // Constructors LStack () { top = null ; size = 0 ; } LStack ( int size ) { top = null ; size = 0 ; } // Reinitialize stack public void clear () { top = null ; size = 0 ; } // Put "it" on stack public boolean push ( E it ) { top = new Link < E > ( it , top ); size ++ ; return true ; } // Remove "it" from stack public E pop () { if ( top == null ) { return null ; } E it = top . element (); top = top . next (); size -- ; return it ; } public E topValue () { // Return top value if ( top == null ) { return null ; } return top . element (); } // Return stack length public int length () { return size ; } // Tell if the stack is empty public boolean isEmpty () { return size == 0 ; } } 

Here is a visual representation for the linked stack. 

# 9. 9.1.1. Linked Stack Push ¶ 

Settings 

Saving... Server Error Resubmit 

# 9. 9.2. Linked Stack Pop ¶ 

Settings 

Saving... Server Error Resubmit 

# 9. 9.2.1. Comparison of Array-Based and Linked Stacks ¶ 

All operations for the array-based and linked stack implementations
take constant time, so from a time efficiency perspective,
neither has a significant advantage.
Another basis for comparison is the total space
required.
The analysis is similar to that done for list implementations.
The array-based stack must declare a fixed-size array initially, and
some of that space is wasted whenever the stack is not full.
The linked stack can shrink and grow but requires the overhead of a
link field for every element. 

When implementing multiple stacks, sometimes you can take advantage of
the one-way growth of the array-based stack
by using a single array to store two stacks.
One stack grows inward from each end as illustrated by the figure
below, hopefully leading to less wasted space.
However, this only works well when the space requirements of the two
stacks are inversely correlated.
In other words, ideally when one stack grows, the other will shrink.
This is particularly effective when elements are taken from
one stack and given to the other.
If instead both stacks grow at the same time, then the free space
in the middle of the array will be exhausted quickly. 

Privacy | | License « 9. 8. Stacks :: Contents :: 9. 10. Freelists » 

Contact Us | | Report a bug 
© Copyright 2011-2025 by OpenDSA Project Contributors and distributed under an MIT license.
      Last updated on Oct 15, 2025.
      Created using Sphinx 8.2.0. 

Summary*: Operating system*: Windows Mac OS Linux iOS Android Other Browser*: Chrome Safari Internet Explorer Opera Other Description*: Attach a screenshot (optional):
