from __future__ import annotations

import json
from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService


@AgentRegistry.register
class QuizAgent(BaseAgent):
    name = "QuizAgent"
    description = "基于知识点生成结构化练习题"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge_name = str(context.params.get("knowledge_name") or "").strip()
        if not knowledge_name:
            return self.error_result(message="缺少 knowledge_name 参数")

        question_types = self._question_types(context.params.get("question_types"))
        difficulty = str(context.params.get("difficulty") or "medium")
        count = self._count(context.params.get("count"))

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="QuizAgent",
            scene="quiz.generate",
            params={
                "knowledge_name": knowledge_name,
                "knowledge_description": context.params.get("knowledge_description") or "暂无补充描述",
                "question_types": ", ".join(question_types),
                "difficulty": difficulty,
                "count": count,
            },
        )

        llm = get_llm_provider(
            db=self.db,
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.run_id,
            prompt_version_id=rendered.prompt_version_id,
        )
        response = await llm.chat(
            [ChatMessage(role="user", content=rendered.content)],
            temperature=0.4,
            max_tokens=4096,
        )
        questions = self._parse_questions(
            response.content,
            knowledge_name=knowledge_name,
            question_types=question_types,
            difficulty=difficulty,
            count=count,
        )

        return self.success_result(
            data={
                "title": f"{knowledge_name}练习",
                "questions": questions,
                "model_name": response.model,
                "prompt_version_id": str(rendered.prompt_version_id) if rendered.prompt_version_id else None,
                "agent_run_id": str(context.run_id) if context.run_id else None,
            },
            message="练习题生成成功",
            evidence=[f"基于知识点「{knowledge_name}」生成 {len(questions)} 道题"],
        )

    def _parse_questions(
        self,
        text: str,
        *,
        knowledge_name: str,
        question_types: list[str],
        difficulty: str,
        count: int,
    ) -> list[dict[str, Any]]:
        cleaned = self._strip_json_fence(text)
        data: object = None
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = None

        if isinstance(data, dict):
            raw_items = data.get("questions") or data.get("quizzes") or []
        elif isinstance(data, list):
            raw_items = data
        else:
            raw_items = []

        questions: list[dict[str, Any]] = []
        if isinstance(raw_items, list):
            for index, item in enumerate(raw_items[:count]):
                if isinstance(item, dict):
                    questions.append(self._normalize_item(
                        item,
                        index=index,
                        knowledge_name=knowledge_name,
                        question_type=question_types[index % len(question_types)],
                        difficulty=difficulty,
                    ))

        while len(questions) < count:
            index = len(questions)
            questions.append(self._fallback_question(
                index=index,
                knowledge_name=knowledge_name,
                question_type=question_types[index % len(question_types)],
                difficulty=difficulty,
            ))
        return questions

    def _normalize_item(
        self,
        item: dict[str, Any],
        *,
        index: int,
        knowledge_name: str,
        question_type: str,
        difficulty: str,
    ) -> dict[str, Any]:
        question_text = str(item.get("question_text") or item.get("stem") or "").strip()
        standard_answer = str(item.get("standard_answer") or item.get("correct_answer") or "").strip()
        if not question_text or not standard_answer:
            return self._fallback_question(
                index=index,
                knowledge_name=knowledge_name,
                question_type=question_type,
                difficulty=difficulty,
            )
        return {
            "question_type": str(item.get("question_type") or question_type),
            "difficulty": str(item.get("difficulty") or difficulty),
            "question_text": question_text,
            "options": item.get("options") or [],
            "standard_answer": standard_answer,
            "analysis": str(item.get("analysis") or item.get("explanation") or "请结合课程资料复盘该题。"),
            "error_tags": item.get("error_tags") if isinstance(item.get("error_tags"), list) else ["概念理解偏差"],
            "created_by": "ai",
        }

    def _fallback_question(
        self,
        *,
        index: int,
        knowledge_name: str,
        question_type: str,
        difficulty: str,
    ) -> dict[str, Any]:
        if question_type in {"single_choice", "multiple_choice"}:
            return {
                "question_type": question_type,
                "difficulty": difficulty,
                "question_text": f"第 {index + 1} 题：学习「{knowledge_name}」时，哪一项做法最有助于形成可迁移理解？",
                "options": {
                    "A": "只记忆术语定义",
                    "B": "把定义、操作过程、复杂度和典型应用连起来理解",
                    "C": "跳过边界条件",
                    "D": "只看答案不做推演",
                },
                "standard_answer": "B",
                "analysis": f"{knowledge_name}需要通过定义、过程、复杂度和应用场景形成完整理解。",
                "error_tags": ["概念理解偏差", "迁移能力不足"],
                "created_by": "system",
            }
        return {
            "question_type": question_type,
            "difficulty": difficulty,
            "question_text": f"第 {index + 1} 题：请简述「{knowledge_name}」的核心定义和一个典型应用。",
            "options": [],
            "standard_answer": f"应说明{knowledge_name}的定义、关键操作或性质，并给出一个典型应用。",
            "analysis": "简答题重点检查是否能把概念和应用联系起来。",
            "error_tags": ["表达不完整", "应用场景不足"],
            "created_by": "system",
        }

    def _strip_json_fence(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
            return "\n".join(lines).strip()
        return cleaned

    def _question_types(self, value: object) -> list[str]:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return items or ["single_choice"]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return ["single_choice"]

    def _count(self, value: object) -> int:
        try:
            return max(1, min(20, int(value)))
        except (TypeError, ValueError):
            return 5
