# Schemas Layer

Pydantic DTOs live here.

Responsibilities:
- Define request bodies, response payloads, and validation shapes.
- Keep API wire formats aligned with `docs/11_API接口设计/`.
- Avoid database access, business orchestration, and external API calls.

Typical naming:
- File: `wiki.py`
- Classes: `WikiPageCreate`, `WikiPageUpdate`, `WikiPageRead`
