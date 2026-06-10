---
source_id: open-data-structures
source_type: open_textbook
chapter_id: ch04
license: CC BY
source_url: https://opendatastructures.org/ods-python/
attribution: Open Data Structures (in pseudocode)
imported_at: 2026-06-06T17:44:44.557481+00:00
text_hash: 229d4909731c2c66364a7dda6887ebeb8b24fa87b9d66e31c3a3f5798e66ec04
---

# linked lists

3. Linked Lists 
Next: 3.1 SLList: A Singly-Linked Up: Open Data Structures (in Previous: 2.7 Discussion and Exercises Contents Index 

# 3 . Linked Lists 

In this chapter, we continue to study implementations of the List
interface, this time using pointer-based data structures rather than
arrays.  The structures in this chapter are made up of nodes that
contain the list items.  Using references (pointers), the nodes are
linked together into a sequence.  We first study singly-linked lists,
which can implement Stack and (FIFO) Queue operations in constant
time per operation and then move on to doubly-linked lists, which can
implement Deque operations in constant time. 
Linked lists have advantages and disadvantages when compared to array-based
implementations of the List interface.  The primary disadvantage is that
we lose the ability to access any element using or in constant time.  Instead, we have to walk through the list, one element
at a time, until we reach the th element.  The primary advantage is
that they are more dynamic:  Given a reference to any list node , we
can delete or insert a node adjacent to in constant time. This
is true no matter where is in the list. 
Subsections 
3 . 1 SLList: A Singly-Linked List 
3 . 2 DLList: A Doubly-Linked List 
3 . 3 SEList: A Space-Efficient Linked List 
3 . 4 Discussion and Exercises 
Next: 3.1 SLList: A Singly-Linked Up: Open Data Structures (in Previous: 2.7 Discussion and Exercises Contents Index opendatastructures.org
