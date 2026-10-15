from __future__ import annotations

import json
import re
from typing import Any

from uuid import UUID

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.agents.structured_chat_utils import call_structured_chat_or_none
from app.agents.structured_outputs import MemoryReflectOutput
from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage
from app.services.prompt_service import PromptService
from app.services.memory_facts import learning_memory_source_allowed


@AgentRegistry.register
class MemoryAgent(BaseAgent):
    name = "MemoryAgent"
    description = "从学习记录中生成长期记忆"

    async def run(self, context: AgentContext) -> AgentResult:
        action = context.params.get("action", "reflect")

        if action == "reflect":
            return await self._reflect(context)

        return self.error_result(message=f"不支持的操作: {action}")

    async def _reflect(self, context: AgentContext) -> AgentResult:
        from app.services.memory_reflection_service import MemoryReflectionService
        course_id_str = context.params.get("course_id")
        scoped_course_id: UUID | None = UUID(str(course_id_str)) if course_id_str else None
        counts = await MemoryReflectionService(self.db).reflect_scope(
            user_id=context.user_id, course_id=scoped_course_id,
        )
        return self.success_result(
            data={"created_count": counts["created"], "reinforced_count": counts["reinforced"], "processed_jobs": counts["jobs"]},
            message=f"反思完成，处理 {counts['jobs']} 条记录，新增 {counts['created']} 条，强化 {counts['reinforced']} 条记忆",
        )

    async def extract_candidates(self, user_id: UUID, records: list[Any]) -> list[dict[str, Any]]:
        if not records:
            return []
        provider = get_llm_provider(db=self.db, user_id=user_id)
        from app.llm.adapters.mock_provider import MockLLMProvider

        if isinstance(provider, MockLLMProvider):
            return self._rule_based_reflect(records)
        return await self._llm_reflect(provider, records, user_id=user_id)

    async def _llm_reflect(
        self, provider: Any, records: list[Any], *, user_id: UUID
    ) -> list[dict[str, Any]]:
        records = [record for record in records if record.event_type != "chat"
                   or learning_memory_source_allowed(str((record.event_payload or {}).get("question") or ""))]
        if not records:
            return []
        record_texts = []
        for r in records:
            record_texts.append(
                f"- [source_id={r.id}, event_type={r.event_type}] {json.dumps(r.event_payload, ensure_ascii=False)[:300]}"
            )
        records_text = "\n".join(record_texts) if record_texts else "暂无记录"
        if hasattr(self.db, "execute"):
            from app.repositories.memory_repository import MemoryRepository
            from app.services.memory_service import MemoryService

            course_id = getattr(records[0], "course_id", None)
            known = await MemoryRepository(self.db).reconciliation_candidates(user_id, course_id)
            active = [{"id": str(item.id), "memory_type": item.memory_type, "content": item.content[:250]}
                      for item in known if item.status == "active"][:50]
            suppressed = [MemoryService.build_fact_key(item.memory_type, item.content, item.memory_key)
                          for item in known if item.status == "forgotten"]
            records_text += "\n已有记忆（只用于对齐）：" + json.dumps(active, ensure_ascii=False)
            records_text += "\n已遗忘规范键（禁止重建）：" + json.dumps(suppressed, ensure_ascii=False)

        rendered = await PromptService(self.db).render_prompt(
            agent_name="MemoryAgent", scene="memory.extract",
            params={"records_text": records_text},
        )
        structured = await call_structured_chat_or_none(
            provider,
            [ChatMessage(role="user", content=rendered.content)],
            MemoryReflectOutput,
            temperature=0.3,
            max_tokens=1024,
            max_retries=1,
            thinking={"type": "disabled"},
            prompt_version_id=rendered.prompt_version_id,
        )
        if structured is not None:
            return [item.model_dump(exclude_none=True) for item in structured.memories]
        return self._rule_based_reflect(records)

    def _rule_based_reflect(self, records: list[Any]) -> list[dict[str, Any]]:
        if not records:
            return []
        memories: list[dict[str, Any]] = []
        for record in records:
            payload = record.event_payload or {}
            if record.event_type != "chat":
                continue
            question = str(payload.get("question") or "").strip()
            if not learning_memory_source_allowed(question):
                continue
            match = re.search(r"(?:我更喜欢|我喜欢|记住我喜欢)(用例子|举例子|用图|画图|分步骤|用代码|简短|详细)(?:讲|解释|回答|说明)?", question)
            if match:
                memories.append({
                    "memory_type": "preference",
                    "content": f"学生明确要求后续讲解{match.group(1)}。",
                    "evidence": [str(record.id)],
                    "confidence": 0.9,
                })
        return memories
