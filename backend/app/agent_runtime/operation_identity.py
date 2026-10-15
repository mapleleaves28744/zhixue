from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def operation_key(state: dict[str, Any], name: str, arguments: dict[str, Any]) -> str:
    frame = state.get("intent_frame_v1") or {}
    topic = str(arguments.get("topic") or arguments.get("concept") or arguments.get("goal") or "").strip().casefold()
    tasks = [item for item in frame.get("tasks", []) if name in item.get("tools", [])]
    matches = [item for item in tasks if str(item.get("topic", "")).strip().casefold() == topic]
    if matches or len(tasks) == 1:
        assigned = {item.get("operation_key") for item in state.get("tool_calls", [])}
        candidates = matches or tasks
        prefix = f"op:r{frame.get('revision', 1)}:"
        selected = next((item for item in candidates if f"{prefix}{item['id']}:{name}" not in assigned), candidates[0])
        return f"op:r{frame.get('revision', 1)}:{selected['id']}:{name}"
    # Unknown contracts still reuse an identical parameterized operation.
    identity = json.dumps({"tool": name, "arguments": arguments}, sort_keys=True, ensure_ascii=False)
    return "op:" + str(uuid5(NAMESPACE_URL, identity))
