from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.prompt_renderer import PromptRenderer
from app.models.prompt import PromptVersion


DEFAULT_PROMPTS: dict[tuple[str, str], str] = {
    (
        "KnowledgeAgent",
        "knowledge.normalize",
    ): (
        "你是课程知识结构编辑。请把候选整理为细粒度、规范、可生成 Wiki 的知识点。\n"
        "目标保留 {min_items}-{max_items} 个；不足时不得虚构。\n"
        "可以合并同义项、规范名称、划分章节和父知识点。"
        "每个保留项只能引用输入中的 source_chunk_ids，禁止无来源新增概念。"
        "拒绝 Markdown 标记、半句话、操作说明和模板措辞。\n\n"
        "候选：{candidates}"
    ),
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
        "你是课程 AI Tutor。先直接回答，再给必要解释。\n"
        "课程资料支持的关键结论必须在句末标注 [S1]、[S2]；只能使用输入中存在的编号。\n"
        "没有可信课程依据时，明确写出‘课程资料未找到可靠依据’，并把通用知识放在‘通用知识补充’段落。\n"
        "不要编造来源，不要输出独立引用清单。\n\n"
        "问题：{question}\n\n"
        "编号课程证据：\n{retrieved_context}\n\n"
        "知识关系：\n{graph_context}\n\n"
        "学生画像：\n{student_profile}\n\n"
        "长期记忆：\n{memory_context}"
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
        "QuizAgent",
        "quiz.generate",
    ): (
        "你是数据结构课程的 Quiz Agent。请围绕知识点生成结构化练习题。\n\n"
        "知识点：{knowledge_name}\n"
        "知识点描述：{knowledge_description}\n"
        "题型：{question_types}\n"
        "难度：{difficulty}\n"
        "数量：{count}\n\n"
        "请只返回 JSON，不要添加 Markdown 解释。格式如下：\n"
        "{{\n"
        "  \"questions\": [\n"
        "    {{\n"
        "      \"question_type\": \"single_choice\",\n"
        "      \"difficulty\": \"medium\",\n"
        "      \"question_text\": \"题干\",\n"
        "      \"options\": {{\"A\": \"选项A\", \"B\": \"选项B\", \"C\": \"选项C\", \"D\": \"选项D\"}},\n"
        "      \"standard_answer\": \"B\",\n"
        "      \"analysis\": \"解析与正确思路\",\n"
        "      \"error_tags\": [\"概念理解偏差\"]\n"
        "    }}\n"
        "  ]\n"
        "}}\n\n"
        "题型契约：\n"
        "- single_choice：options 为 A/B/C/D 对象，standard_answer 为单个选项字母。\n"
        "- multiple_choice：options 为 A/B/C/D 对象，standard_answer 为多个选项字母组合，例如 AC。\n"
        "- judge：options 为 {{\"正确\":\"正确\",\"错误\":\"错误\"}}，standard_answer 为 正确 或 错误。\n"
        "- short_answer：options 为空数组，standard_answer 为简短参考答案。\n"
        "- fill_blank：题干必须包含 ____，options 为空数组，standard_answer 为填空答案。\n"
        "- coding：options 为空数组，standard_answer 描述关键伪代码步骤和边界条件。\n\n"
        "要求：题目必须和知识点直接相关；客观题答案必须唯一且可批改；解析要说明依据；错因标签要可用于错题本。"
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


GROUNDED_TUTOR_RULES = (
    "\n\n强制引用规则：课程依据必须使用当前输入中的 [S#]；"
    "不得引用不存在的编号；没有可信证据时必须明确说明课程依据不足。"
)


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

    async def render_grounded_tutor_prompt(
        self,
        params: dict[str, Any],
    ) -> RenderedPrompt:
        rendered = await self.render_prompt(
            agent_name="TutorAgent",
            scene="tutor.qa",
            params=params,
        )
        return RenderedPrompt(
            content=f"{rendered.content}{GROUNDED_TUTOR_RULES}",
            prompt_version_id=rendered.prompt_version_id,
            source=rendered.source,
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
