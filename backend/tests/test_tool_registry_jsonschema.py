import pytest
from uuid import UUID

from app.agent_runtime.tools import AgentTool, ToolContext, ToolExecutionResult, ToolRegistry


async def dummy(ctx, args):
    return ToolExecutionResult(output={"ok": True})


@pytest.mark.asyncio
async def test_tool_registry_rejects_invalid_enum():
    registry = ToolRegistry()
    registry.register(AgentTool(
        name="demo",
        description="demo",
        agent_name="TestAgent",
        input_schema={
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["a", "b"]}},
            "required": ["mode"],
            "additionalProperties": False,
        },
        handler=dummy,
    ))
    result = await registry.execute(
        "demo",
        {"mode": "c"},
        ToolContext(
            task_id=UUID("00000000-0000-0000-0000-000000000001"),
            conversation_id=UUID("00000000-0000-0000-0000-000000000002"),
            tool_call_id="call_1",
            user_id=UUID("00000000-0000-0000-0000-000000000003"),
            course_id=UUID("00000000-0000-0000-0000-000000000004"),
        ),
    )
    assert result.success is False
    assert "校验失败" in (result.error_message or "")
