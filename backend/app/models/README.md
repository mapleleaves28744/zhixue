# Models Layer

SQLAlchemy ORM models live here.

Responsibilities:
- Define database table mappings and relationships.
- Keep table names, fields, indexes, and constraints aligned with migrations.
- Avoid business workflows, permission checks, and request parsing.

Typical naming:
- File: `wiki.py`
- Class: `WikiPage`
- Table: `wiki_pages`
