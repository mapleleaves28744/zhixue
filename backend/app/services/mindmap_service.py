from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage
from app.models.user import User
from app.repositories.resource_repository import ResourceRepository
from app.services.diagram_service import CONCISE_MERMAID_RULES


class MindmapService:
    """Generate Mermaid mindmap resources grounded in course retrieval."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        scope: str = "course",
        depth: int = 3,
    ) -> dict[str, Any]:
        topic = topic.strip() or "数据结构知识结构"
        depth = max(2, min(5, int(depth)))
        knowledge_items = await KnowledgeSearchService(self.db).search(
            current_user=current_user,
            course_id=course_id,
            query=topic,
            top_k=15,
        )
        response = await get_llm_provider(
            db=self.db,
            user_id=current_user.id,
            course_id=course_id,
        ).chat(
            [ChatMessage(role="user", content=self._build_prompt(topic, knowledge_items, depth))],
            temperature=0.5,
            max_tokens=4096,
        )
        mermaid_code = self._extract_mermaid(response.content, topic)
        citations = self._build_citations(knowledge_items, topic=topic, scope=scope, depth=depth)
        resource = await ResourceRepository(self.db).create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="mindmap",
            title=f"{topic} 知识思维导图",
            content=mermaid_code,
            citations=citations,
            personalized_reason=f"基于课程检索片段生成，范围={scope}，深度={depth}",
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
            "topic": topic,
        }

    def _build_prompt(self, topic: str, knowledge_items: list[dict[str, Any]], depth: int) -> str:
        context = "\n".join(
            f"- {item.get('source_title') or '课程资料'}: {str(item.get('content') or '')[:200]}"
            for item in knowledge_items[:10]
        )
        return (
            f"请围绕「{topic}」生成一个 Mermaid mindmap 思维导图。\n\n"
            f"参考知识片段：\n{context or '暂无检索片段'}\n\n"
            f"要求：\n"
            f"1. 使用 Mermaid mindmap 语法\n"
            f"2. 最大深度 {depth} 层\n"
            f"3. 中心节点为「{topic}」\n"
            f"4. {CONCISE_MERMAID_RULES}\n"
            f"5. 只输出 Mermaid 代码，不要其他解释\n"
        )

    def _extract_mermaid(self, content: str, topic: str = "知识结构") -> str:
        match = re.search(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        if "mindmap" in content:
            return content[content.index("mindmap") :].strip()
        cleaned = content.strip()
        if cleaned.startswith("mindmap"):
            return cleaned
        return f"mindmap\n  root({topic})\n    AI推断内容\n      建议核对资料"

    def _build_citations(
        self,
        knowledge_items: list[dict[str, Any]],
        *,
        topic: str,
        scope: str,
        depth: int,
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
                "title": "mindmap_generation",
                "extra": {"topic": topic, "scope": scope, "depth": depth},
            }
        )
        return citations
