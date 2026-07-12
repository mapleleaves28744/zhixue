from __future__ import annotations

from typing import Any

from app.agent_runtime.tools import AgentTool, ToolRegistry


def register_tool(
    registry: ToolRegistry,
    name: str,
    description: str,
    agent_name: str,
    properties: dict[str, Any],
    required: list[str],
    handler: Any,
    *,
    writes_db: bool = False,
    risk_level: str = "low",
    requires_confirmation: bool = False,
    timeout_seconds: int = 120,
) -> None:
    registry.register(
        AgentTool(
            name=name,
            description=description,
            agent_name=agent_name,
            input_schema={
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            handler=handler,
            writes_db=writes_db,
            risk_level=risk_level,  # type: ignore[arg-type]
            requires_confirmation=requires_confirmation,
            timeout_seconds=timeout_seconds,
        )
    )
