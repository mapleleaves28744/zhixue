from __future__ import annotations

import json
from collections import Counter
from typing import Any

from uuid import UUID

from sqlalchemy import select

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.agents.structured_chat_utils import call_structured_chat_or_none
from app.agents.structured_outputs import MemoryReflectOutput
from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage


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
        from app.models.learning_record import LearningRecord
        from app.models.memory import MemoryReflectionState
        from app.services.memory_service import MemoryService

        course_id_str = context.params.get("course_id")
        scoped_course_id: UUID | None = UUID(str(course_id_str)) if course_id_str else None
        state_condition = [MemoryReflectionState.user_id == context.user_id]
        state_condition.append(
            MemoryReflectionState.course_id == scoped_course_id
            if scoped_course_id
            else MemoryReflectionState.course_id.is_(None)
        )
        state = (await self.db.execute(select(MemoryReflectionState).where(*state_condition))).scalar_one_or_none()
        stmt = (
            select(LearningRecord)
            .where(LearningRecord.user_id == context.user_id)
            .order_by(LearningRecord.created_at.asc())
            .limit(100)
        )
        if scoped_course_id:
            stmt = stmt.where(LearningRecord.course_id == scoped_course_id)
        if state and state.last_record_created_at:
            stmt = stmt.where(LearningRecord.created_at > state.last_record_created_at)
        result = await self.db.execute(stmt)
        records = list(result.scalars().all())

        provider = get_llm_provider(db=self.db, user_id=context.user_id)
        from app.llm.adapters.mock_provider import MockLLMProvider

        if isinstance(provider, MockLLMProvider):
            memories_data = self._rule_based_reflect(records)
        else:
            memories_data = await self._llm_reflect(provider, records)

        memory_service = MemoryService(self.db)
        actions: list[str] = []
        for m in memories_data:
            _, action = await memory_service.upsert_memory(
                user_id=context.user_id,
                course_id=scoped_course_id,
                memory_type=m.get("memory_type", "insight"),
                content=m.get("content", ""),
                evidence=MemoryService.normalize_evidence(m.get("evidence", [])),
                confidence=m.get("confidence", 0.8),
            )
            actions.append(action)

        if records:
            if state is None:
                state = MemoryReflectionState(user_id=context.user_id, course_id=scoped_course_id)
                self.db.add(state)
            state.last_record_created_at = records[-1].created_at
            state.last_record_id = records[-1].id

        await self.db.commit()

        return self.success_result(
            data={"created_count": actions.count("add"), "reinforced_count": actions.count("reinforce")},
            message=f"反思完成，新增 {actions.count('add')} 条，强化 {actions.count('reinforce')} 条记忆",
        )

    async def _llm_reflect(
        self, provider: Any, records: list[Any]
    ) -> list[dict[str, Any]]:
        record_texts = []
        for r in records[:30]:
            record_texts.append(
                f"- [{r.event_type}] {json.dumps(r.event_payload, ensure_ascii=False)[:150]}"
            )
        records_text = "\n".join(record_texts) if record_texts else "暂无记录"

        prompt = (
            "你是一个学习分析引擎。根据学习记录，提取长期记忆。\n"
            "返回 JSON 对象，包含 memories 数组；每项含 memory_type、content、evidence、confidence。\n\n"
            f"学习记录：\n{records_text}"
        )
        structured = await call_structured_chat_or_none(
            provider,
            [ChatMessage(role="user", content=prompt)],
            MemoryReflectOutput,
            temperature=0.3,
            max_tokens=1024,
        )
        if structured is not None and structured.memories:
            return [item.model_dump(exclude_none=True) for item in structured.memories]
        response = await provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=1024,
        )
        try:
            result = json.loads(response.content)
            if isinstance(result, dict) and isinstance(result.get("memories"), list):
                return result["memories"]
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        return self._rule_based_reflect(records)

    def _rule_based_reflect(self, records: list[Any]) -> list[dict[str, Any]]:
        if not records:
            return []

        type_counter = Counter(r.event_type for r in records)
        total = len(records)
        memories = []

        dominant = type_counter.most_common(1)[0]
        if dominant[1] >= 3:
            memories.append({
                "memory_type": "preference",
                "content": f"该学生主要通过 '{dominant[0]}' 类型活动学习（占比 {dominant[1]}/{total}），建议强化此路径。",
                "evidence": [f"event_type={dominant[0]}, count={dominant[1]}"],
                "confidence": 0.75,
            })

        error_records = [
            r for r in records
            if r.event_type in ("practice_error", "quiz_wrong")
        ]
        if error_records:
            memories.append({
                "memory_type": "mistake_pattern",
                "content": f"近期有 {len(error_records)} 条错误记录，建议重点复习相关知识点。",
                "evidence": [str(r.id) for r in error_records[:5]],
                "confidence": 0.7,
            })

        if total >= 10:
            memories.append({
                "memory_type": "insight",
                "content": f"累计 {total} 条学习记录，学习活跃度较高。",
                "evidence": [f"total_records={total}"],
                "confidence": 0.9,
            })

        return memories
