from __future__ import annotations

import json
from typing import Any

from app.agent_runtime import supervisor_intents
from app.llm.schemas import ChatMessage, ToolCall
from app.services.context_budget import estimate_tokens, input_token_limit


def _artifact_brief(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"reference": str(value)[:120]}
    return {
        key: str(value[key])[:160]
        for key in ("type", "subtype", "id", "asset_id", "title", "status")
        if value.get(key) is not None
    }


def _observation_brief(item: dict[str, Any]) -> dict[str, Any]:
    output = item.get("output")
    if isinstance(output, dict):
        output_preview = {
            str(key)[:40]: str(value)[:180]
            for key, value in list(output.items())[:4]
            if key not in {"content", "markdown", "chunks", "items"}
        }
    else:
        output_preview = str(output or "")[:240]
    return {
        "tool_call_id": str(item.get("tool_call_id") or "")[:128],
        "tool_name": str(item.get("tool_name") or "")[:80],
        "success": bool(item.get("success")),
        "artifact_refs": [_artifact_brief(value) for value in list(item.get("artifact_refs") or [])[:3]],
        "error": str(item.get("error_message") or "")[:240],
        "output_preview": output_preview,
    }


def _bounded_view(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return str(value)[:160]
    if isinstance(value, dict):
        return {str(key)[:60]: _bounded_view(item, depth=depth + 1)
                for key, item in list(value.items())[:12]}
    if isinstance(value, list):
        return [_bounded_view(item, depth=depth + 1) for item in value[:8]]
    return value[:600] if isinstance(value, str) else value


def build_messages(state: dict[str, Any], *, schema_token_reserve: int = 0) -> list[ChatMessage]:
    system = (
        "你是智学工坊 Supervisor Agent。你的职责是根据用户目标、历史消息和工具观察，"
        "**直接通过原生 function calling 选择下一步工具**。"
        "优先调用有来源的知识检索工具；工具失败后调整方案，不要重复无效调用。"
        "交付物必须与用户意图一致：语音→synthesize_speech，"
        "PPT/幻灯片/课件/slides/deck/keynote/网页ppt→generate_interactive_courseware（多页 HTML 互动课件，不是视频），"
        "插图→generate_educational_image，流程图→generate_diagram，思维导图→generate_mindmap，练习→generate_quiz，"
        "纯答疑→answer_course_question，文字讲解资源→generate_explanation。"
        "用户一句话包含多个交付物（如「二叉树 ppt 和队列思维导图」）时，必须分别调用对应工具，"
        "每个工具的 topic/concept 只用该子任务的主题词，不要把整句当 topic。"
        "讲解视频与沉浸课堂生成已下线，不要选择相关工具。"
        "禁止把文字资源、Markdown 或摘要冒充语音/视频/图片结果。"
        "当用户要求语音时，先准备讲解文本（检索/生成），再 synthesize_speech。"
        "当用户要求插图/知识卡片时：有文生图 API 则 generate_educational_image；"
        "无 API 时同一工具会自动产出简明 Mermaid 知识卡片（思维导图或流程图）。"
        "Mermaid 与文生图均应保持节点/元素简明，复杂知识用多层而非单节点堆字。"
        "只有在任务真正完成、且不需要再调用工具时，才返回纯文本 final_answer。"
        "若仍需工具，请直接发起 tool call，不要只返回 JSON 计划。"
        "不要输出隐式思维链，只输出简洁决策摘要。"
    )
    goal = str(state.get("goal") or "")
    profile_only = supervisor_intents.is_profile_update_only_goal(goal)
    recommended = supervisor_intents.plan_required_tools(goal, is_profile_update_only=profile_only)
    older_requests = [
        str(item.get("content") or "")[:80]
        for item in (state.get("messages") or [])[:-12]
        if item.get("role") == "user"
    ]
    context = {
        "goal": state.get("goal"),
        "recommended_tools": recommended,
        "recommended_tool_labels": [supervisor_intents.deliverable_label(name) for name in recommended],
        "tool_topics": state.get("tool_topics") or supervisor_intents.parse_tool_topics(goal),
        "parsed_intents": state.get("parsed_intents") or [
            {"segment": item.segment, "topic": item.topic, "tools": list(item.tools)}
            for item in supervisor_intents.parse_goal_intents(goal)
        ],
        "intent_frame": [
            {
                "id": str(task.get("id") or "")[:32],
                "topic": str(task.get("topic") or "")[:120],
                "tools": list(task.get("tools") or [])[:5],
            }
            for task in (state.get("intent_frame_v1") or {}).get("tasks") or []
        ][:8],
        "current_plan": [str(item)[:180] for item in (state.get("current_plan") or [])[:12]],
        "observations": [_observation_brief(item) for item in (state.get("observations") or [])[-8:]],
        "artifacts": [_artifact_brief(value) for value in list(state.get("artifacts") or [])[-12:]],
        "learning_context": _bounded_view(state.get("context") or {}),
        "older_user_requests": list(dict.fromkeys(older_requests[:4] + older_requests[-10:])),
        "iteration_count": state.get("iteration_count") or 0,
    }
    messages = [ChatMessage(role="system", content=system)]
    messages.extend(
        ChatMessage(role=str(item.get("role") or "user"), content=str(item.get("content") or ""))
        for item in (state.get("messages") or [])[-12:]
    )
    observations_by_call = {
        str(item.get("tool_call_id")): item
        for item in state.get("observations") or []
        if item.get("tool_call_id")
    }
    paired = [
        (call, observations_by_call[str(call.get("id"))])
        for call in state.get("tool_calls") or []
        if call.get("id") and str(call.get("id")) in observations_by_call
    ][-4:]
    for call, observation in paired:
        call_id = str(call["id"])
        messages.append(ChatMessage(
            role="assistant", content="",
            tool_calls=[ToolCall(id=call_id, name=str(call.get("name") or ""), arguments=dict(call.get("arguments") or {}))],
        ))
        messages.append(ChatMessage(
            role="tool", tool_call_id=call_id,
            content=json.dumps(_observation_brief(observation), ensure_ascii=False),
        ))
    messages.append(ChatMessage(role="user", content=f"当前任务状态：{json.dumps(context, ensure_ascii=False)}"))
    # Preserve the current task and paired tool messages; shed older dialogue
    # when its estimated size exceeds the shared input budget.
    input_limit = input_token_limit(output_reserve=3072, schema_reserve=schema_token_reserve)
    while sum(estimate_tokens(item.content) for item in messages) > input_limit and len(messages) > 2:
        if len(messages) > 3 and (
            (messages[1].role == "user" and messages[2].role == "assistant")
            or (messages[1].role == "assistant" and messages[2].role == "tool")
        ):
            del messages[1:3]
        else:
            del messages[1]
    return messages
