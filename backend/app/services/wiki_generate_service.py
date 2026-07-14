from __future__ import annotations

import json
import logging
import re
from typing import Any
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
from app.services.wiki_service import describe_wiki_page_quality

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

        knowledge_points = await self.knowledge.list_by_owner(course_id, owner_id)
        knowledge_points = self._filter_material_knowledge_points(knowledge_points, material_id)
        if not knowledge_points:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="当前资料尚无已整理知识点，请先执行知识点抽取",
                status_code=400,
            )

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
                source_chunks = self._source_chunks_for_point(kp, chunks)
                related_chunks = [chunk.content for chunk in source_chunks]
                if not related_chunks:
                    related_chunks = [chunk.content for chunk in chunks[:3]]
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
                page.knowledge_id = kp.id

                await self.wiki.create_source(
                    page_id=page.id,
                    source_type="knowledge_point",
                    source_id=kp.id,
                    source_title=kp.name,
                )
                for chunk in self._source_chunks_for_point(kp, chunks):
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

    async def rebuild_low_quality_pages(
        self,
        *,
        course_id: UUID,
        owner_id: UUID,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> list[dict[str, Any]]:
        """Rebuild legacy low-quality pages sequentially from the course corpus.

        A page is only changed after its replacement has enough real source chunks
        and passes the same display-quality rule used by the student UI.  Each
        successful page receives a new version, so the original text is retained.
        """
        pages, _ = await self.wiki.list_by_owner(
            owner_id=owner_id,
            course_id=course_id,
            status="active",
            page=1,
            page_size=500,
        )
        targets = [
            page
            for page in pages
            if describe_wiki_page_quality(page)["status"] == "needs_enrichment"
        ]
        chunks = await self.chunks.list_by_course(course_id)
        points = await self.knowledge.list_by_owner(course_id, owner_id)
        points_by_id = {point.id: point for point in points}
        points_by_name = {point.name: point for point in points}
        results: list[dict[str, Any]] = []
        eligible_rebuild_count = 0

        for page in targets:
            page_id = page.id
            page_title = page.title
            point = points_by_id.get(page.knowledge_id) or points_by_name.get(page.title)
            source_chunks = self._source_chunks_for_point(point, chunks) if point else []
            source_strategy = "knowledge_binding" if source_chunks else ""
            if not source_chunks:
                source_chunks = self._select_rebuild_source_chunks(page.title, chunks)
                source_strategy = "title_match" if source_chunks else ""
            source_chunks = source_chunks[:5]
            if not source_chunks:
                results.append({
                    "page_id": str(page.id),
                    "title": page.title,
                    "status": "skipped",
                    "reason": "当前课程没有可验证的关联资料切片",
                })
                continue

            if limit is not None and eligible_rebuild_count >= max(0, limit):
                break
            eligible_rebuild_count += 1

            if dry_run:
                results.append({
                    "page_id": str(page.id),
                    "title": page.title,
                    "status": "pending",
                    "source_chunk_count": len(source_chunks),
                    "source_strategy": source_strategy,
                })
                continue

            try:
                description = getattr(point, "description", None) or page.summary
                source_text = self._rebuild_source_text(source_chunks)
                generated_content = await self._generate_content(
                    page.title,
                    description,
                    source_text,
                    course_id=course_id,
                    owner_id=owner_id,
                )
                content = self._ensure_rebuild_content(
                    generated_content,
                    page.title,
                    description,
                    source_chunks,
                )
                versions = await self.wiki.list_versions(page_id)
                new_version = self._next_rebuild_version(page.current_version, versions)
                summary = self._rebuild_summary(page.title, description, content)
                extra_meta = dict(page.extra_meta or {})
                extra_meta["last_course_material_rebuild"] = {
                    "version": new_version,
                    "source_chunk_count": len(source_chunks),
                    "source_strategy": source_strategy,
                    "strategy": "sequential_low_quality_rebuild_v1",
                }
                await self.wiki.update_page(
                    page,
                    content=content,
                    summary=summary,
                    current_version=new_version,
                    extra_meta=extra_meta,
                )
                await self.wiki.create_version(
                    page_id=page_id,
                    version_number=new_version,
                    title=page.title,
                    content=content,
                    summary=summary,
                    change_message="基于课程资料逐页补强",
                    created_by=owner_id,
                )
                existing_source_keys = {
                    (source.source_type, str(source.source_id))
                    for source in (page.sources or [])
                }
                if point and ("knowledge_point", str(point.id)) not in existing_source_keys:
                    await self.wiki.create_source(
                        page_id=page.id,
                        source_type="knowledge_point",
                        source_id=point.id,
                        source_title=point.name,
                    )
                for chunk in source_chunks:
                    source_key = ("chunk", str(chunk.id))
                    if source_key in existing_source_keys:
                        continue
                    await self.wiki.create_source(
                        page_id=page.id,
                        source_type="chunk",
                        source_id=chunk.id,
                        source_title=chunk.source_title,
                        quote_text=chunk.content[:300],
                    )
                await self.db.commit()
                rebuilt_page = await self.wiki.get_by_id(page_id)
                quality = describe_wiki_page_quality(rebuilt_page or page)
                results.append({
                    "page_id": str(page_id),
                    "title": page_title,
                    "status": "rebuilt" if quality["status"] == "verified" else "review_needed",
                    "version": new_version,
                    "source_chunk_count": len(source_chunks),
                    "quality": quality,
                })
            except Exception as error:
                await self.db.rollback()
                logger.exception("逐页补强 Wiki 失败: %s", page_id)
                results.append({
                    "page_id": str(page_id),
                    "title": page_title,
                    "status": "failed",
                    "reason": str(error),
                })
        return results

    @staticmethod
    def _filter_material_knowledge_points(
        knowledge_points: list[object],
        material_id: UUID,
    ) -> list[object]:
        material_key = str(material_id)
        return [
            point
            for point in knowledge_points
            if material_key
            in (
                ((getattr(point, "extra_meta", None) or {}).get("normalization") or {}).get(
                    "source_material_ids", []
                )
            )
        ]

    @staticmethod
    def _source_chunks_for_point(point: object, chunks: list[object]) -> list[object]:
        source_ids = {
            str(chunk_id)
            for chunk_id in (
                ((getattr(point, "extra_meta", None) or {}).get("normalization") or {}).get(
                    "source_chunk_ids", []
                )
            )
        }
        if source_ids:
            return [chunk for chunk in chunks if str(getattr(chunk, "id", "")) in source_ids]
        point_id = getattr(point, "id", None)
        return [chunk for chunk in chunks if getattr(chunk, "knowledge_id", None) == point_id]

    @staticmethod
    def _select_rebuild_source_chunks(title: str, chunks: list[object]) -> list[object]:
        """Only use chunks that explicitly mention the page title or its base term."""
        normalized_title = title.strip().lower()
        base_title = re.sub(r"\s*\([^)]*\)", "", normalized_title).replace("入门", "").strip()
        terms = [term for term in dict.fromkeys([normalized_title, base_title]) if term]
        ranked = sorted(
            chunks,
            key=lambda chunk: (
                -sum(str(getattr(chunk, "content", "")).lower().count(term) for term in terms),
                getattr(chunk, "chunk_index", 0),
            ),
        )
        matching = [
            chunk
            for chunk in ranked
            if any(term in str(getattr(chunk, "content", "")).lower() for term in terms)
        ]
        return matching[:5]

    @staticmethod
    def _rebuild_source_text(chunks: list[object]) -> str:
        return "\n\n".join(
            f"[课程资料：{getattr(chunk, 'source_title', None) or '资料切片'}]\n{str(getattr(chunk, 'content', ''))[:1200]}"
            for chunk in chunks
        )[:5000]

    @classmethod
    def _ensure_rebuild_content(
        cls,
        content: str,
        title: str,
        description: str | None,
        chunks: list[object],
    ) -> str:
        normalized = str(content or "").strip()
        section_count = sum(1 for line in normalized.splitlines() if line.strip().startswith("##"))
        if len(normalized) >= 300 and section_count >= 2:
            return normalized
        return cls._rebuild_template_content(title, description, chunks)

    @staticmethod
    def _rebuild_template_content(title: str, description: str | None, chunks: list[object]) -> str:
        description_text = description or f"围绕「{title}」的课程知识点。"
        excerpts = "\n\n".join(
            f"> {str(getattr(chunk, 'content', '')).strip()[:500]}"
            for chunk in chunks[:3]
            if str(getattr(chunk, "content", "")).strip()
        ) or "> 当前资料未提供可展示的摘录。"
        source_names = "、".join(
            dict.fromkeys(
                str(getattr(chunk, "source_title", "") or "课程资料")
                for chunk in chunks[:3]
            )
        )
        return (
            f"# {title}\n\n"
            f"## 定义\n\n{description_text}\n\n"
            f"## 核心内容\n\n以下要点来自当前课程资料，学习时应结合原文理解：\n\n{excerpts}\n\n"
            "## 示例与理解\n\n请将上面的资料片段与本章操作、图示或练习题对应起来，先说明概念的输入、过程和结果，再验证自己是否能复述关键规则。\n\n"
            "## 学习建议\n\n1. 用自己的话复述定义和关键规则。\n2. 对照资料中的例子，写出每一步状态变化。\n3. 完成一道同类练习后再回看易混淆点。\n\n"
            f"## 来源说明\n\n本页依据课程资料切片生成：{source_names}。如资料未覆盖的延伸结论，应标为 AI 推断并回到原资料核对。"
        )

    @staticmethod
    def _rebuild_summary(title: str, description: str | None, content: str) -> str:
        if description:
            return str(description)[:180]
        plain = re.sub(r"[#>*`_]+", "", content).replace("\n", " ").strip()
        return (plain or f"基于课程资料补强的「{title}」Wiki 页面")[:180]

    @staticmethod
    def _next_rebuild_version(current_version: int, versions: list[object]) -> int:
        historical_versions = [
            int(getattr(version, "version_number", 0) or 0)
            for version in versions
        ]
        return max([int(current_version or 0), *historical_versions], default=0) + 1

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
