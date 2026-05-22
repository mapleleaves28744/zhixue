# Utils Layer

Shared helper utilities live here.

Responsibilities:
- Provide small reusable helpers for parsing, formatting, IDs, time handling, or file helpers.
- Keep utilities stateless where possible.
- Avoid business workflows, database access, and API response handling.

If a helper starts depending on domain rules, move it into the related service.
