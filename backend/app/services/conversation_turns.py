from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompletedTurn:
    user: Any
    assistant: Any


def _request_key(message: Any) -> tuple[str, str] | None:
    task_id = getattr(message, "task_id", None)
    if task_id is not None:
        return "task", str(task_id)
    payload = getattr(message, "payload", {}) or {}
    request_id = getattr(message, "client_request_id", None) or payload.get("client_request_id")
    if request_id is not None:
        return "request", str(request_id)
    return None


def completed_turn_blocks(messages: list[Any]) -> list[tuple[int, list[CompletedTurn]]]:
    """Only expose a coverage boundary once every preceding user turn is complete."""
    pending: list[Any] = []
    current: list[CompletedTurn] = []
    blocks: list[tuple[int, list[CompletedTurn]]] = []
    for message in messages:
        role = str(getattr(message, "role", ""))
        if role == "user":
            pending.append(message)
            continue
        if role != "assistant" or not pending:
            continue
        key = _request_key(message)
        match = next((index for index, item in enumerate(pending) if _request_key(item) == key), None) if key else None
        if key and match is None:
            # Older Tutor messages had an assistant request ID but no user ID.
            # Never attach a mismatched keyed reply to another in-flight turn.
            match = next((index for index, item in enumerate(pending) if _request_key(item) is None), None)
            if match is None:
                continue
        user = pending.pop(match if match is not None else 0)
        current.append(CompletedTurn(user=user, assistant=message))
        if not pending:
            current.sort(key=lambda pair: int(getattr(pair.user, "sequence_no", 0)))
            blocks.append((int(getattr(message, "sequence_no", 0)), current))
            current = []
    return blocks
