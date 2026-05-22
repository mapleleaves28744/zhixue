# Repositories Layer

Database access code lives here.

Responsibilities:
- Encapsulate SQLAlchemy queries, filters, pagination, creates, updates, and deletes.
- Avoid business decisions, permission policy, LLM calls, and request parsing.
- Return ORM models or repository-level data structures for services to interpret.

Typical naming:
- File: `wiki_repository.py`
- Class: `WikiRepository`
