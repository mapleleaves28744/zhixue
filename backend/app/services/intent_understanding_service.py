from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal
from pydantic import BaseModel, Field
from app.agent_runtime.intent_contract import IntentFrame, IntentSubtask, NON_ARTIFACT_TOOLS
from app.services.conversation_context_service import ConversationContext
from app.services.prompt_service import PromptService
from app.llm.schemas import ChatMessage

logger = logging.getLogger(__name__)


class SemanticSubtask(BaseModel):
    topic: str = Field(min_length=1, max_length=240)
    segment: str = Field(min_length=1, max_length=500)
    tools: list[str] = Field(min_length=1, max_length=10)


class SemanticIntent(BaseModel):
    mode: Literal["answer", "execute", "clarify"]
    tasks: list[SemanticSubtask] = Field(default_factory=list, max_length=8)
    clarification_question: str | None = Field(default=None, max_length=300)
    unresolved_slots: list[str] = Field(default_factory=list, max_length=8)
    resolved_goal: str | None = Field(default=None, max_length=5000)


def needs_semantic_understanding(goal: str, frame: dict[str, Any], context: ConversationContext) -> bool:
    if len(frame.get("tasks") or []) > 1 or "学生最新修订" in goal:
        return True
    if any(word in goal for word in ("各", "分别")) and any(word in goal for word in ("和", "与", "、")):
        return True
    if frame.get("mode") == "clarify":
        return bool(context.last_question)
    # Candidate topic extraction is deliberately narrow. Route natural delivery
    # requests and explicit missing-topic statements through semantic validation,
    # even when the rule parser produced a plausible but polluted topic.
    if re.search(r"(?:还没|尚未|没有).{0,8}(?:选定|确定|选好).{0,8}(?:知识点|主题)", goal):
        return True
    if frame.get("tasks") and re.search(r"讲解资源|自测题|面向初学者|^(?:为|替我|帮我准备)", goal.strip()):
        return True
    if any(re.search(r"\s|^(?:请|为|围绕|针对|关于|帮)|(?:资料|资源|自测题|讲解)", str(task.get("topic") or ""))
           for task in frame.get("tasks") or []):
        return True
    if context.last_question and re.search(r"刚才|上面|同类|这个|那个|上一", goal):
        return True
    return not frame.get("tasks") and bool(re.match(r"^(?:帮我|替我|据此|改成|调整为|沿用|按刚才)", goal.strip()))


class IntentUnderstandingService:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def resolve(self, *, goal: str, frame: dict[str, Any], context: ConversationContext,
                      provider: Any, tools: list[dict[str, Any]]) -> dict[str, Any]:
        actual_provider = getattr(provider, "inner", provider)
        if not needs_semantic_understanding(goal, frame, context) or getattr(actual_provider, "provider_name", "") == "mock":
            return frame
        allowed = {item["function"]["name"] for item in tools} - set(frame.get("exclusions") or [])
        latest = re.split(r"学生最新修订[（(]优先于之前要求[）)][:：]", goal)[-1].strip()
        revised = latest != goal.strip()
        try:
            prompt = await PromptService(self.db).render_prompt(
                agent_name="OrchestratorAgent", scene="intent.understand",
                params={"goal": latest, "context": context.render()[:6000], "tools": json.dumps(sorted(allowed), ensure_ascii=False)},
            )
            parsed = await provider.structured_chat(
                [ChatMessage(role="user", content=prompt.content)], SemanticIntent,
                temperature=0, max_tokens=1800, max_retries=1, thinking={"type": "disabled"},
                prompt_version_id=prompt.prompt_version_id,
            )
            if parsed.mode == "execute" and any(name not in allowed for item in parsed.tasks for name in item.tools):
                raise ValueError("semantic intent selected unavailable tool")
            if parsed.mode == "execute" and not parsed.tasks:
                raise ValueError("execute requires a deliverable")
            if parsed.mode == "clarify" and not parsed.clarification_question:
                raise ValueError("clarification requires a question")
            source = latest if revised else latest + "\n" + context.render()
            def normalize(value: str) -> str:
                return re.sub(r"\s+", "", value).casefold()
            aliases = {"bfs": "广度优先搜索", "dfs": "深度优先搜索", "快排": "快速排序", "bst": "二叉搜索树"}
            source_text = normalize(source)
            # Answer-mode descriptions may combine comparison topics. They never
            # authorize tools and are discarded below; validate executable topics.
            for task in parsed.tasks if parsed.mode == "execute" else []:
                topic = normalize(task.topic)
                if topic not in source_text and aliases.get(topic, topic) not in source_text:
                    raise ValueError("semantic topic has no current source")
            original = IntentFrame.model_validate(frame)
            tasks = [IntentSubtask(
                id=f"s{index}", topic=item.topic, segment=item.segment, tools=item.tools,
                source_message_id=original.original_request_message_id or original.request_message_id,
                acceptance={"kind": "tool_result" if all(name in NON_ARTIFACT_TOOLS for name in item.tools) else "tool_result_and_artifact", "topic": item.topic},
            ) for index, item in enumerate(parsed.tasks, 1)] if parsed.mode == "execute" else []
            return original.model_copy(update={
                "parser": "semantic_v1", "mode": parsed.mode, "tasks": tasks,
                "clarification_question": parsed.clarification_question,
                "unresolved_slots": parsed.unresolved_slots, "uncertainty": [],
                "resolved_goal": latest if revised else parsed.resolved_goal,
            }).model_dump(mode="json")
        except Exception as exc:
            logger.warning("Semantic intent validation failed (%s); using conservative fallback", type(exc).__name__)
            # Partial/ambiguous rule candidates cannot authorize wrong delivery
            # after semantic validation fails. Revisions cannot revive old goals.
            polluted = any(re.search(r"\s|^(?:请|为|围绕|针对|关于|帮)", str(task.get("topic") or ""))
                           for task in frame.get("tasks") or [])
            combination = any(word in goal for word in ("各", "分别")) and any(word in goal for word in ("和", "与", "、"))
            if revised or polluted or combination:
                return {**frame, "mode": "clarify", "tasks": [], "unresolved_slots": ["topic_or_deliverable"],
                        "clarification_question": "请把要处理的知识点和交付形式分别写清楚，例如栈的讲解、队列的练习题。",
                        "uncertainty": [*(frame.get("uncertainty") or []), "semantic_understanding_unavailable"]}
            return {**frame, "uncertainty": [*(frame.get("uncertainty") or []), "semantic_understanding_unavailable"]}
