from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage
from app.models.user import User
from app.repositories.resource_repository import ResourceRepository
from app.services.knowledge_search_service import KnowledgeSearchService
from app.services.visual_search_context import search_items


# 知识卡片生成约束：复杂度过高会导致文生图乱码或 Mermaid 渲染拥挤
CONCISE_MERMAID_RULES = (
    "节点标签尽量短（每个不超过 10 个汉字）；"
    "可多层展开，但每层分支不超过 5 个；"
    "总节点数不超过 15 个；"
    "优先表达核心概念与关系，细节放文字讲解而非图中。"
)

CONCISE_IMAGE_CARD_RULES = (
    "单张简明知识卡片：扁平教育插画，留白充足；"
    "最多 3–4 个视觉元素；"
    "文字标签短、对比清晰；"
    "避免拥挤、过多箭头或过细线条（易乱码/乱套）。"
)

DIAGRAM_PROMPTS = {
    "flowchart": "生成一个 Mermaid flowchart TD 流程图，展示 {concept} 的执行流程或逻辑关系。",
    "sequence": "生成一个 Mermaid sequenceDiagram 时序图，展示 {concept} 中各组件的交互过程。",
    "class": "生成一个 Mermaid classDiagram 类图，展示 {concept} 的结构和关系。",
    "er": "生成一个 Mermaid erDiagram 实体关系图，展示 {concept} 的数据模型。",
}

DIAGRAM_PREFIXES = {
    "flowchart": "flowchart TD",
    "sequence": "sequenceDiagram",
    "class": "classDiagram",
    "er": "erDiagram",
}


class DiagramService:
    """Generate Mermaid diagram resources for course concepts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate(
        self,
        *,
        current_user: User,
        course_id: UUID,
        concept: str,
        diagram_type: str = "flowchart",
        requirement: str | None = None,
    ) -> dict[str, Any]:
        concept = concept.strip() or "数据结构概念"
        diagram_type = diagram_type if diagram_type in DIAGRAM_PROMPTS else "flowchart"
        search_payload = await KnowledgeSearchService(self.db).search(
            current_user=current_user,
            course_id=course_id,
            query=concept,
            top_k=12,
        )
        knowledge_items = search_items(search_payload)
        response = await get_llm_provider(
            db=self.db,
            user_id=current_user.id,
            course_id=course_id,
        ).chat(
            [ChatMessage(role="user", content=self._build_prompt(concept, diagram_type, knowledge_items, requirement=requirement))],
            temperature=0.5,
            max_tokens=4096,
        )
        mermaid_code = self._extract_mermaid(response.content, concept=concept, diagram_type=diagram_type)
        citations = self._build_citations(knowledge_items, concept=concept, diagram_type=diagram_type)
        resource = await ResourceRepository(self.db).create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="diagram",
            title=f"{concept} 图解说明",
            content=mermaid_code,
            citations=citations,
            personalized_reason=f"基于课程检索片段生成 Mermaid {diagram_type} 图解",
            model_name=response.model,
            prompt_version_id=None,
        )
        await self.db.commit()
        await self.db.refresh(resource)
        return {
            "resource_id": str(resource.id),
            "title": resource.title,
            "mermaid_code": mermaid_code,
            "content": mermaid_code,
            "citations": citations,
            "concept": concept,
            "diagram_type": diagram_type,
        }

    def _build_prompt(
        self,
        concept: str,
        diagram_type: str,
        knowledge_items: list[dict[str, Any]],
        requirement: str | None = None,
    ) -> str:
        context = "\n".join(
            f"- {item.get('source_title') or '课程资料'}: {str(item.get('content') or '')[:200]}"
            for item in knowledge_items[:8]
        )
        instruction = DIAGRAM_PROMPTS[diagram_type].format(concept=concept)
        return (
            f"{instruction}\n\n"
            f"参考知识片段：\n{context or '暂无检索片段'}\n\n"
            f"用户指定步骤：{str(requirement or '无').strip() or '无'}\n\n"
            f"要求：只输出 Mermaid 代码；{CONCISE_MERMAID_RULES} "
            "无法从资料确认的内容标注为 AI 推断内容。"
        )

    def _extract_mermaid(self, content: str, *, concept: str, diagram_type: str) -> str:
        match = re.search(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        prefix = DIAGRAM_PREFIXES[diagram_type]
        if prefix in content:
            return content[content.index(prefix) :].strip()
        cleaned = content.strip()
        if cleaned.startswith(prefix):
            return cleaned
        if diagram_type == "sequence":
            return f"sequenceDiagram\n  participant S as 学生\n  participant K as {concept}\n  S->>K: 学习概念\n  K-->>S: 返回关键步骤"
        return f"flowchart TD\n  A[{concept}] --> B[核心概念]\n  B --> C[操作过程]\n  C --> D[AI推断内容 建议核对资料]"

    def _build_citations(
        self,
        knowledge_items: list[dict[str, Any]],
        *,
        concept: str,
        diagram_type: str,
    ) -> list[dict[str, Any]]:
        citations = [
            {
                "source_type": "document",
                "title": item.get("source_title") or "课程资料",
                "source_id": item.get("material_id"),
                "chunk_id": item.get("chunk_id"),
                "page_no": item.get("page_no"),
                "score": item.get("score"),
                "quote": str(item.get("content") or "")[:240],
            }
            for item in knowledge_items[:8]
        ]
        if not citations:
            citations.append(
                {
                    "source_type": "inference",
                    "title": "AI 推断内容，建议核对资料",
                    "quote": "当前未检索到可引用课程片段。",
                }
            )
        citations.append(
            {
                "source_type": "generation_config",
                "title": "diagram_generation",
                "extra": {"concept": concept, "diagram_type": diagram_type},
            }
        )
        return citations
