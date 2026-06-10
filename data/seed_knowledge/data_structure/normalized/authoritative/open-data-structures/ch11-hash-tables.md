---
source_id: open-data-structures
source_type: open_textbook
chapter_id: ch11
license: CC BY
source_url: https://opendatastructures.org/ods-python/
attribution: Open Data Structures (in pseudocode)
imported_at: 2026-06-06T17:44:44.551795+00:00
text_hash: 48c6e24f7c8576389587dfb9f7079bf677796fc65f0784ba9be0e84866fbb6ff
---

# hash tables

5. Hash Tables 
Next: 5.1 ChainedHashTable: Hashing with Up: Open Data Structures (in Previous: 4.5 Discussion and Exercises Contents Index 

# 5 . Hash Tables 

Hash tables are an efficient method of storing a small number, , of integers from a large range .
The term hash table includes a broad range of data structures.  The first part of this
chapter focuses on two of the most common implementations of hash tables:
hashing with chaining and linear probing. 
Very often hash tables store types of data that are not integers.
In this case, an integer hash code is associated with each data
item and is used in the hash table.  The second part of this chapter
discusses how such hash codes are generated. 
Some of the methods used in this chapter require random choices of
integers in some specific range.  In the code samples, some of these
``random'' integers are hard-coded constants.  These constants were
obtained using random bits generated from atmospheric noise. 
Subsections 
5 . 1 ChainedHashTable: Hashing with Chaining 
5 . 2 LinearHashTable: Linear Probing 
5 . 3 Hash Codes 
5 . 4 Discussion and Exercises opendatastructures.org
