from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm import ChatMessage, get_llm_provider
from app.models.wiki import WikiPage
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.wiki_repository import WikiRepository
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class WikiGenerateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.materials = MaterialRepository(db)
        self.chunks = ChunkRepository(db)
        self.knowledge = KnowledgeRepository(db)
        self.wiki = WikiRepository(db)
        self.llm = get_llm_provider(db=db)
        self.prompts = PromptService(db)

    async def generate_from_material(
        self,
        course_id: UUID,
        material_id: UUID,
        owner_id: UUID,
    ) -> list[WikiPage]:
        material = await self.materials.get_by_id(material_id)
        if material is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="资料不存在",
                status_code=404,
            )
        if material.course_id != course_id:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="资料不属于该课程",
                status_code=400,
            )

        # Get chunks and knowledge points
        chunks = await self.chunks.list_by_material(material_id)
        if not chunks:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="资料尚未切片，请先执行 chunk 操作",
                status_code=400,
            )

        knowledge_points = await self.knowledge.list_by_course(course_id)
        if not knowledge_points:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="课程尚无知识点，请先执行知识点抽取",
                status_code=400,
            )

        # Build chunk content by knowledge point
        chunks_by_kp: dict[UUID | None, list[str]] = {}
        for chunk in chunks:
            kid = chunk.knowledge_id
            chunks_by_kp.setdefault(kid, []).append(chunk.content)

        created_pages: list[WikiPage] = []

        # Filter out knowledge points that already have wiki pages
        pending_kps = []
        for kp in knowledge_points:
            slug = self._slugify(kp.name)
            existing = await self.wiki.find_by_slug(course_id, owner_id, slug)
            if existing:
                created_pages.append(existing)
            else:
                pending_kps.append(kp)

        if not pending_kps:
            return created_pages

        # Batch generate: up to 8 knowledge points per LLM call
        BATCH_SIZE = 8
        for batch_start in range(0, len(pending_kps), BATCH_SIZE):
            batch = pending_kps[batch_start : batch_start + BATCH_SIZE]

            # Build batch prompt with all knowledge points
            kp_entries = []
            for kp in batch:
                related_chunks = chunks_by_kp.get(kp.id, [])
                if not related_chunks:
                    related_chunks = chunks_by_kp.get(None, [])[:3]
                chunk_text = "\n\n".join(related_chunks[:5])
                kp_entries.append({
                    "name": kp.name,
                    "description": kp.description or "无",
                    "chunk_text": chunk_text[:2000],
                })

            batch_results = await self._generate_batch(
                kp_entries,
                course_id=course_id,
                owner_id=owner_id,
            )

            # Create pages from batch results
            for kp, result in zip(batch, batch_results):
                slug = self._slugify(kp.name)
                content = result.get("content", self._template_content(
                    kp.name, kp.description, ""
                ))

                page = await self.wiki.create_page(
                    course_id=course_id,
                    owner_id=owner_id,
                    title=kp.name,
                    content=content,
                    summary=kp.description or f"知识点：{kp.name}",
                    slug=slug,
                )

                await self.wiki.create_source(
                    page_id=page.id,
                    source_type="knowledge_point",
                    source_id=kp.id,
                    source_title=kp.name,
                )
                for chunk in chunks:
                    if chunk.knowledge_id == kp.id:
                        await self.wiki.create_source(
                            page_id=page.id,
                            source_type="chunk",
                            source_id=chunk.id,
                            source_title=chunk.source_title or material.file_name,
                            quote_text=chunk.content[:200],
                        )

                created_pages.append(page)

        # Create links between pages based on knowledge point hierarchy
        for kp in knowledge_points:
            if kp.parent_id:
                source_page = await self.wiki.find_by_slug(
                    course_id, owner_id, self._slugify(kp.name)
                )
                parent_kp = next(
                    (k for k in knowledge_points if k.id == kp.parent_id), None
                )
                if parent_kp and source_page:
                    target_page = await self.wiki.find_by_slug(
                        course_id, owner_id, self._slugify(parent_kp.name)
                    )
                    if target_page:
                        await self.wiki.create_link(
                            source_page_id=source_page.id,
                            target_page_id=target_page.id,
                            relation_type="prerequisite",
                        )

        await self.db.commit()
        for page in created_pages:
            await self.db.refresh(page)
        return created_pages

    async def _generate_batch(
        self,
        kp_entries: list[dict],
        *,
        course_id: UUID,
        owner_id: UUID,
    ) -> list[dict]:
        """Generate wiki content for multiple knowledge points in one LLM call."""
        entries_text = ""
        for i, entry in enumerate(kp_entries, 1):
            entries_text += (
                f"\n---\n### 知识点 {i}: {entry['name']}\n"
                f"描述: {entry['description']}\n"
                f"相关资料:\n{entry['chunk_text'][:1500]}\n"
            )

        prompt = (
            f"你是一个数据结构课程的 Wiki 编辑。请为以下 {len(kp_entries)} 个知识点分别生成 Wiki 页面内容。\n"
            f"每个页面包含：定义、核心内容、学习建议。\n"
            f"请严格返回 JSON 数组，每个元素包含 name 和 content 字段。\n\n"
            f"知识点列表：\n{entries_text}\n\n"
            f"返回格式：\n```json\n[{{\"name\": \"知识点名\", \"content\": \"# 标题\\n\\n## 定义\\n...\\n\\n## 核心内容\\n...\\n\\n## 学习建议\\n...\"}}]\n```"
        )

        try:
            response = await self.llm.chat(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.7,
                max_tokens=4096,
                user_id=owner_id,
                course_id=course_id,
            )
            return self._parse_batch_response(response.content, kp_entries)
        except Exception:
            logger.exception("LLM 批量生成 Wiki 失败，使用模板")
            return [
                {"name": e["name"], "content": self._template_content(e["name"], e["description"], e["chunk_text"])}
                for e in kp_entries
            ]

    def _parse_batch_response(self, text: str, kp_entries: list[dict]) -> list[dict]:
        """Parse LLM batch response into list of {name, content} dicts."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            if isinstance(data, list):
                # Match results to entries by index
                results = []
                for i, entry in enumerate(kp_entries):
                    if i < len(data) and isinstance(data[i], dict):
                        results.append({
                            "name": data[i].get("name", entry["name"]),
                            "content": data[i].get("content", ""),
                        })
                    else:
                        results.append({
                            "name": entry["name"],
                            "content": self._template_content(entry["name"], entry["description"], entry["chunk_text"]),
                        })
                return results
        except json.JSONDecodeError:
            pass

        # Fallback: return template for all entries
        return [
            {"name": e["name"], "content": self._template_content(e["name"], e["description"], e["chunk_text"])}
            for e in kp_entries
        ]

    async def _generate_content(
        self,
        name: str,
        description: str | None,
        chunk_text: str,
        *,
        course_id: UUID,
        owner_id: UUID,
    ) -> str:
        rendered = await self.prompts.render_prompt(
            agent_name="WikiAgent",
            scene="wiki.generate",
            params={
                "knowledge_name": name,
                "knowledge_description": description or "无",
                "chunk_text": chunk_text[:3000],
            },
        )
        try:
            response = await self.llm.chat(
                [ChatMessage(role="user", content=rendered.content)],
                temperature=0.7,
                max_tokens=2048,
                user_id=owner_id,
                course_id=course_id,
                prompt_version_id=rendered.prompt_version_id,
            )
            return response.content
        except Exception:
            logger.exception("LLM 生成 Wiki 内容失败，使用模板")
            return self._template_content(name, description, chunk_text)

    def _template_content(
        self, name: str, description: str | None, chunk_text: str
    ) -> str:
        desc = description or "暂无描述"
        excerpt = chunk_text[:500] if chunk_text else "暂无相关资料"
        return (
            f"# {name}\n\n"
            f"## 定义\n\n{desc}\n\n"
            f"## 核心内容\n\n"
            f"以下是与该知识点相关的资料片段：\n\n"
            f"> {excerpt}\n\n"
            f"## 学习建议\n\n"
            f"1. 理解基本概念和定义\n"
            f"2. 结合实际案例加深理解\n"
            f"3. 通过练习巩固知识点\n"
        )

    def _slugify(self, title: str) -> str:
        slug = title.strip().lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug[:255] or "page"
