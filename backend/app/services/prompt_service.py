from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.prompt_renderer import PromptRenderer
from app.models.prompt import PromptVersion


DEFAULT_PROMPTS: dict[tuple[str, str], str] = {
    (
        "WikiAgent",
        "wiki.generate",
    ): (
        "请根据课程资料为知识点「{knowledge_name}」生成 LLM Wiki 页面。\n\n"
        "知识点描述：{knowledge_description}\n\n"
        "相关资料片段：\n{chunk_text}\n\n"
        "要求：输出 Markdown，包含定义、核心内容、示例、学习建议和来源说明。"
        "如果依据不足，必须写明“AI 推断内容，建议核对资料”。"
    ),
    (
        "WikiAgent",
        "wiki.summarize",
    ): (
        "请为以下 Wiki 页面生成不超过 200 字的摘要。\n\n"
        "标题：{title}\n\n"
        "内容：\n{content}"
    ),
    (
        "WikiAgent",
        "wiki.merge_note",
    ): (
        "请将学生笔记整理并融入现有 Wiki 页面，输出完整 Markdown。\n\n"
        "标题：{title}\n\n"
        "## 现有内容\n{existing_content}\n\n"
        "## 学生笔记\n{note_content}\n\n"
        "要求：保留原有结构，新增内容需要自然融入；无法从资料确认的内容标记为 AI 推断内容。"
    ),
    (
        "TutorAgent",
        "tutor.qa",
    ): (
        "你是数据结构课程的 AI Tutor。请基于课程资料、Wiki 和学生画像回答问题。\n\n"
        "问题：{question}\n\n"
        "检索资料：\n{retrieved_context}\n\n"
        "回答必须包含：直接解答、关键依据、相关知识点、后续练习建议。依据不足时明确说明。"
    ),
    (
        "ResourceAgent",
        "resource.generate",
    ): (
        "请为学生生成个性化学习资源。\n\n"
        "知识点：{knowledge_name}\n"
        "资源类型：{resource_type}\n"
        "学生状态：{student_profile}\n"
        "学生附加要求：{requirement}\n\n"
        "关联 Wiki 内容：\n{wiki_context}\n\n"
        "参考资料：\n{context}\n\n"
        "输出 Markdown，必须结构清晰，包含定义/要点/例子或练习建议。"
        "结尾必须包含“个性化原因”和“引用来源”两个小节；没有可靠资料时标注“AI 推断内容，建议核对资料”。"
    ),
    (
        "PlannerAgent",
        "plan.learning",
    ): (
        "请根据学生画像和课程知识点，为学生生成学习路径推荐理由。\n\n"
        "学习目标：{learning_goal}\n"
        "可用时间：{available_time}\n"
        "学生画像：\n{student_profile}\n\n"
        "要求：输出一段不超过 120 字的推荐理由，必须提到薄弱点、知识顺序或 Wiki 依据之一。"
    ),
    (
        "DiagnosisAgent",
        "diagnosis.generate",
    ): (
        "请根据答题记录、错题模式和学习行为生成学习诊断。\n\n"
        "输入数据：{diagnosis_context}\n\n"
        "输出薄弱点、错因模式、证据和下一步建议。"
    ),
    (
        "EvolutionAgent",
        "evolution.analyze",
    ): (
        "请分析是否需要更新学习策略。自进化只能更新画像、偏好、Prompt 参数和推荐策略，不能修改代码、数据库结构或权限。\n\n"
        "证据：{evidence}\n\n"
        "输出 change_summary、before_snapshot、after_snapshot、risk_level 和 rollback 说明。"
    ),
    (
        "ReviewAgent",
        "review.check",
    ): (
        "请审查 AI 生成内容是否有来源、是否偏离知识点、是否存在明显幻觉以及风险等级是否合理。\n\n"
        "待审查内容：{content}\n\n"
        "输出 pass、issues、risk_level 和 revision_suggestions。"
    ),
}


@dataclass
class RenderedPrompt:
    content: str
    prompt_version_id: object | None = None
    source: str = "default"


class PromptService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.renderer = PromptRenderer()

    async def render_prompt(
        self,
        *,
        agent_name: str,
        scene: str,
        params: dict[str, Any],
    ) -> RenderedPrompt:
        version = await self.get_active_prompt(agent_name=agent_name, scene=scene)
        if version is not None:
            return RenderedPrompt(
                content=self.renderer.render(version.template_content, params),
                prompt_version_id=version.id,
                source="database",
            )

        template = self._default_template(agent_name=agent_name, scene=scene)
        return RenderedPrompt(
            content=self.renderer.render(template, params),
            prompt_version_id=None,
            source="default",
        )

    async def get_active_prompt(
        self,
        *,
        agent_name: str,
        scene: str,
    ) -> PromptVersion | None:
        result = await self.db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.agent_name == agent_name,
                PromptVersion.scene == scene,
                PromptVersion.status == "active",
            )
            .order_by(desc(PromptVersion.version_no))
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _default_template(self, *, agent_name: str, scene: str) -> str:
        return DEFAULT_PROMPTS.get(
            (agent_name, scene),
            "请根据以下输入完成任务。\n\n{content}",
        )
