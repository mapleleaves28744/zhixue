---
source_id: opendsa
source_type: interactive_textbook
chapter_id: ch05
license: MIT License
source_url: https://opendsa.org/
attribution: OpenDSA
imported_at: 2026-06-06T17:44:45.004432+00:00
text_hash: 9ce31f4713b06b12a34c43d675618f8d5423065ba4b87a42dfeea76b50d9273c
---

# opendsa array based stack

9.8. Stacks — OpenDSA Data Structures and Algorithms Modules Collection 

# OpenDSA Data Structures and Algorithms Modules Collection 

# Chapter 9 Linear Structures 

| About « 9. 7. List Element Implementations :: Contents :: 9. 9. Linked Stacks » 

# 9. 8. Stacks ¶ 

# 9. 8.1. Stack Terminology and Implementation ¶ 

The stack is a list-like structure
in which elements may be inserted or removed from only one end.
While this restriction makes stacks less flexible than lists,
it also makes stacks both efficient (for those operations they can do)
and easy to implement.
Many applications require only the limited form of
insert and remove operations that stacks provide.
In such cases, it is more efficient to use the simpler stack data
structure rather than the generic list.
For example, the freelist is really a
stack. 

Despite their restrictions, stacks have many uses.
Thus, a special vocabulary for stacks has developed.
Accountants used stacks long before the invention of the computer.
They called the stack a “ LIFO ” list,
which stands for “Last-In, First-Out.”
Note that one implication of the LIFO policy is that stacks
remove elements in reverse order of their arrival. 

The accessible element of the stack is called the top element.
Elements are not said to be inserted, they are pushed onto the stack.
When removed, an element is said to be popped from the
stack.
Here is a simple stack ADT . 

Java 

Java (Generic) 

public interface Stack { // Stack class ADT // Reinitialize the stack. public void clear (); // Push "it" onto the top of the stack public boolean push ( Object it ); // Remove and return the element at the top of the stack public Object pop (); // Return a copy of the top element public Object topValue (); // Return the number of elements in the stack public int length (); // Return true if the stack is empty public boolean isEmpty (); } 

public interface Stack < E > { // Stack class ADT // Reinitialize the stack. public void clear (); // Push "it" onto the top of the stack public boolean push ( E it ); // Remove and return the element at the top of the stack public E pop (); // Return a copy of the top element public E topValue (); // Return the number of elements in the stack public int length (); // Tell if the stack is empty or not public boolean isEmpty (); } 

As with lists, there are many variations on stack implementation.
The two approaches presented here are the array-based stack and the linked stack ,
which are analogous to array-based and linked lists, respectively. 

# 9. 8.1.1. Array-Based Stacks ¶ 

Here is a complete implementation for
the array-based stack class. 

Java 

Java (Generic) 

class AStack implements Stack { private Object stackArray [] ; // Array holding stack private static final int DEFAULT_SIZE = 10 ; private int maxSize ; // Maximum size of stack private int top ; // First free position at top // Constructors AStack ( int size ) { maxSize = size ; top = 0 ; stackArray = new Object [ size ] ; // Create stackArray } AStack () { this ( DEFAULT_SIZE ); } public void clear () { top = 0 ; } // Reinitialize stack // Push "it" onto stack public boolean push ( Object it ) { if ( top >= maxSize ) return false ; stackArray [ top ++] = it ; return true ; } // Remove and return top element public Object pop () { if ( top == 0 ) return null ; return stackArray [-- top ] ; } public Object topValue () { // Return top element if ( top == 0 ) return null ; return stackArray [ top - 1 ] ; } public int length () { return top ; } // Return stack size public boolean isEmpty () { return top == 0 ; } // Check if the stack is empty } 

class AStack < E > implements Stack < E > { private E stackArray [] ; // Array holding stack private static final int DEFAULT_SIZE = 10 ; private int maxSize ; // Maximum size of stack private int top ; // First free position at top // Constructors @SuppressWarnings ( "unchecked" ) // Generic array allocation AStack ( int size ) { maxSize = size ; top = 0 ; stackArray = ( E [] ) new Object [ size ] ; // Create stackArray } AStack () { this ( DEFAULT_SIZE ); } public void clear () { top = 0 ; } // Reinitialize stack // Push "it" onto stack public boolean push ( E it ) { if ( top >= maxSize ) { return false ; } stackArray [ top ++] = it ; return true ; } // Remove and return top element public E pop () { if ( top == 0 ) { return null ; } return stackArray [-- top ] ; } public E topValue () { // Return top element if ( top == 0 ) { return null ; } return stackArray [ top - 1 ] ; } public int length () { return top ; } // Return stack size public boolean isEmpty () { return top == 0 ; } // Tell if the stack is empty } 

Settings 

Saving... Server Error Resubmit 

The array-based stack implementation is essentially
a simplified version of the array-based list.
The only important design decision to be made is which end of the
array should represent the top of the stack. 

Settings 

Saving... Server Error Resubmit 

Settings 

Saving... Server Error Resubmit 

# 9. 8.2. Pop ¶ 

Settings 

Saving... Server Error Resubmit 

Privacy | | License « 9. 7. List Element Implementations :: Contents :: 9. 9. Linked Stacks » 

Contact Us | | Report a bug 
© Copyright 2011-2025 by OpenDSA Project Contributors and distributed under an MIT license.
      Last updated on Oct 15, 2025.
      Created using Sphinx 8.2.0. 

Summary*: Operating system*: Windows Mac OS Linux iOS Android Other Browser*: Chrome Safari Internet Explorer Opera Other Description*: Attach a screenshot (optional):
