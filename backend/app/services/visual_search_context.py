from typing import Any


def search_items(payload: object) -> list[dict[str, Any]]:
    """Normalize knowledge search responses to the item list visual tools consume."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]

    return []
