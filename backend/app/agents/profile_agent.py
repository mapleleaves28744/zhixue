from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage


@AgentRegistry.register
class ProfileAgent(BaseAgent):
    name = "ProfileAgent"
    description = "读取和更新学生画像"

    async def run(self, context: AgentContext) -> AgentResult:
        action = context.params.get("action", "read")

        if action == "read":
            return await self._read(context)
        if action == "rebuild":
            return await self._rebuild(context)

        return self.error_result(message=f"不支持的操作: {action}")

    async def _read(self, context: AgentContext) -> AgentResult:
        from app.models.profile import StudentProfile

        result = await self.db.execute(
            select(StudentProfile).where(StudentProfile.user_id == context.user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return self.success_result(
                data={"profile": None},
                message="学生画像不存在",
            )
        return self.success_result(
            data={
                "profile": {
                    "id": str(profile.id),
                    "major": profile.major,
                    "grade": profile.grade,
                    "learning_goal": profile.learning_goal,
                    "profile_summary": profile.profile_summary,
                    "mastery_snapshot": profile.mastery_snapshot,
                    "weak_points": profile.weak_points,
                    "error_patterns": profile.error_patterns,
                    "strategy_summary": profile.strategy_summary,
                }
            },
            message="学生画像读取成功",
        )

    async def _rebuild(self, context: AgentContext) -> AgentResult:
        from app.models.learning_record import LearningRecord
        from app.models.profile import StudentProfile

        records_result = await self.db.execute(
            select(LearningRecord)
            .where(LearningRecord.user_id == context.user_id)
            .order_by(LearningRecord.created_at.desc())
            .limit(200)
        )
        records = list(records_result.scalars().all())

        record_summaries = []
        for r in records[:50]:
            record_summaries.append(
                f"- [{r.event_type}] {r.event_source or ''}: {json.dumps(r.event_payload, ensure_ascii=False)[:200]}"
            )
        records_text = "\n".join(record_summaries) if record_summaries else "暂无学习记录"

        provider = get_llm_provider(db=self.db, user_id=context.user_id)
        from app.llm.adapters.mock_provider import MockLLMProvider

        if isinstance(provider, MockLLMProvider):
            profile_data = self._rule_based_rebuild(records)
        else:
            profile_data = await self._llm_rebuild(provider, records_text)

        profile_result = await self.db.execute(
            select(StudentProfile).where(StudentProfile.user_id == context.user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            profile = StudentProfile(user_id=context.user_id)
            self.db.add(profile)

        profile.profile_summary = profile_data.get("profile_summary", "")
        profile.mastery_snapshot = profile_data.get("mastery_snapshot", {})
        profile.weak_points = profile_data.get("weak_points", [])
        profile.error_patterns = profile_data.get("error_patterns", [])
        profile.strategy_summary = profile_data.get("strategy_summary", {})
        profile.version_no += 1

        await self.db.commit()
        await self.db.refresh(profile)

        return self.success_result(
            data={"profile_id": str(profile.id), "version_no": profile.version_no},
            message="画像重建完成",
        )

    async def _llm_rebuild(self, provider: Any, records_text: str) -> dict[str, Any]:
        prompt = (
            "你是一个学习分析引擎。根据以下学习记录，生成学生画像 JSON。\n"
            "返回格式（纯 JSON，不要 markdown）：\n"
            '{"profile_summary": "...", "mastery_snapshot": {"知识点": 掌握度0-1}, '
            '"weak_points": ["薄弱点"], "error_patterns": ["错误模式"], '
            '"strategy_summary": {"建议": "..."}}\n\n'
            f"学习记录：\n{records_text}"
        )
        response = await provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=1024,
        )
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return self._rule_based_rebuild([])

    def _rule_based_rebuild(self, records: list[Any]) -> dict[str, Any]:
        event_counts: dict[str, int] = {}
        for r in records:
            event_counts[r.event_type] = event_counts.get(r.event_type, 0) + 1

        total = len(records)
        if total == 0:
            return {
                "profile_summary": "该学生暂无学习记录，建议开始学习以建立画像。",
                "mastery_snapshot": {},
                "weak_points": [],
                "error_patterns": [],
                "strategy_summary": {"建议": "开始学习后系统将自动分析学习模式。"},
            }

        practice_count = event_counts.get("practice", 0)
        qa_count = event_counts.get("qa", 0)

        return {
            "profile_summary": f"基于 {total} 条学习记录的分析：练习 {practice_count} 次，问答 {qa_count} 次。",
            "mastery_snapshot": {},
            "weak_points": ["待更多数据积累后自动识别"],
            "error_patterns": ["待更多练习数据后自动分析"],
            "strategy_summary": {
                "建议": "继续保持学习频率，系统将在积累更多数据后提供精准分析。"
            },
        }
