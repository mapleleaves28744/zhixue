# Services Layer

Business workflows live here.

Responsibilities:
- Coordinate use cases across repositories, agents, providers, storage, and cache.
- Enforce permission context and domain rules before persistence.
- Keep API routers thin by exposing focused service methods.

Services may call repositories, agents, LLM providers, storage utilities, and other services when needed.
