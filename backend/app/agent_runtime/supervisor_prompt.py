from __future__ import annotations

import json
from typing import Any

from app.agent_runtime import supervisor_intents
from app.llm.schemas import ChatMessage, ToolCall


def build_messages(state: dict[str, Any]) -> list[ChatMessage]:
    system = (
        "你是智学工坊 Supervisor Agent。你的职责是根据用户目标、历史消息和工具观察，"
        "**直接通过原生 function calling 选择下一步工具**。"
        "优先调用有来源的知识检索工具；工具失败后调整方案，不要重复无效调用。"
        "交付物必须与用户意图一致：语音→synthesize_speech，普通短视频→generate_lesson_video，"
        "沉浸课堂/一键课程→generate_immersive_classroom，"
        "PPT/幻灯片/课件/slides/deck/keynote/网页ppt→generate_interactive_courseware（多页 HTML 互动课件，不是视频），"
        "插图→generate_educational_image，流程图→generate_diagram，思维导图→generate_mindmap，练习→generate_quiz，"
        "纯答疑→answer_course_question，文字讲解资源→generate_explanation。"
        "用户一句话包含多个交付物（如「二叉树 ppt 和队列思维导图」）时，必须分别调用对应工具，"
        "每个工具的 topic/concept 只用该子任务的主题词，不要把整句当 topic。"
        "用户说「讲解 ppt / 做一份幻灯片 / 课件」时，禁止调用 generate_lesson_video。"
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
    context = {
        "goal": state.get("goal"),
        "recommended_tools": recommended,
        "recommended_tool_labels": [supervisor_intents.deliverable_label(name) for name in recommended],
        "tool_topics": state.get("tool_topics") or supervisor_intents.parse_tool_topics(goal),
        "parsed_intents": state.get("parsed_intents") or [
            {"segment": item.segment, "topic": item.topic, "tools": list(item.tools)}
            for item in supervisor_intents.parse_goal_intents(goal)
        ],
        "current_plan": state.get("current_plan") or [],
        "observations": (state.get("observations") or [])[-8:],
        "artifacts": state.get("artifacts") or [],
        "learning_context": state.get("context") or {},
        "iteration_count": state.get("iteration_count") or 0,
    }
    messages = [ChatMessage(role="system", content=system)]
    messages.extend(
        ChatMessage(role=str(item.get("role") or "user"), content=str(item.get("content") or ""))
        for item in (state.get("messages") or [])[-12:]
    )
    prior_tool_calls = state.get("tool_calls") or []
    observations = state.get("observations") or []
    reasoning_content = state.get("protocol_reasoning_content")
    if reasoning_content and prior_tool_calls and observations:
        last_call = prior_tool_calls[-1]
        messages.append(ChatMessage(
            role="assistant", content="", reasoning_content=str(reasoning_content),
            tool_calls=[ToolCall(id=str(last_call.get("id") or ""), name=str(last_call.get("name") or ""), arguments=dict(last_call.get("arguments") or {}))],
        ))
        messages.append(ChatMessage(role="tool", tool_call_id=str(last_call.get("id") or ""), content=json.dumps(observations[-1], ensure_ascii=False)))
    messages.append(ChatMessage(role="user", content=f"当前任务状态：{json.dumps(context, ensure_ascii=False)}"))
    return messages
