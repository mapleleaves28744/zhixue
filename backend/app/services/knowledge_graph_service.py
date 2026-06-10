from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.knowledge_relation_repository import KnowledgeRelationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.wiki_repository import WikiRepository
from app.llm import ChatMessage, get_llm_provider
from app.services.mastery_service import MasteryService
from app.services.wiki_service import WikiService

BIDIRECTIONAL_RELATION_TYPES = frozenset({"similar", "confused_with", "related"})
DIRECTED_RELATION_TYPES = frozenset(
    {"prerequisite", "next", "used_in", "contains", "belongs_to", "resource_for", "example_of"}
)


class KnowledgeGraphService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.knowledge = KnowledgeRepository(db)
        self.relations = KnowledgeRelationRepository(db)
        self.wiki = WikiService(db)
        self.wiki_repo = WikiRepository(db)
        self.mastery = MasteryService(db)

    async def merge_dialogue_extraction(
        self,
        *,
        current_user: User,
        course_id: UUID,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        dialogue_excerpt: str = "",
    ) -> dict[str, Any]:
        kp_by_name = await self._knowledge_name_index(course_id=course_id, owner_id=current_user.id)
        created_entities = 0
        created_relations = 0
        created_wiki = 0
        touched_ids: list[str] = []

        for raw in entities:
            name = str(raw.get("name") or "").strip()
            if not name:
                continue
            point, is_new = await self.knowledge.create_if_not_exists(
                course_id=course_id,
                owner_id=current_user.id,
                scope="personal",
                name=name,
                description=str(raw.get("description") or "")[:500] or None,
                chapter=str(raw.get("chapter") or "")[:128] or None,
            )
            kp_by_name[name.lower()] = point
            touched_ids.append(str(point.id))
            if is_new:
                created_entities += 1

            new_page = await self._ensure_wiki_for_knowledge(
                current_user=current_user,
                course_id=course_id,
                point=point,
                draft=str(raw.get("wiki_summary") or raw.get("description") or ""),
                dialogue_excerpt=dialogue_excerpt,
            )
            if new_page is not None:
                created_wiki += 1

            await self.mastery.apply_ask_update(
                user_id=current_user.id,
                course_id=course_id,
                knowledge_id=point.id,
                understood=bool(raw.get("understood")),
            )

        created_relations += await self._persist_relations(
            current_user=current_user,
            course_id=course_id,
            relations=relations,
            kp_by_name=kp_by_name,
        )

        await self.mastery.sync_profile_snapshot(user_id=current_user.id, course_id=course_id)
        return {
            "entities_merged": len(entities),
            "relations_merged": len(relations),
            "created_entities": created_entities,
            "created_relations": created_relations,
            "wiki_pages_touched": created_wiki,
            "touched_knowledge_ids": list(dict.fromkeys(touched_ids)),
        }

    async def infer_relations_after_material_extract(
        self,
        *,
        current_user: User,
        course_id: UUID,
        owner_id: UUID,
        material_text: str,
        new_points: list[Any],
    ) -> int:
        """资料抽取后：对照已有知识点，由 AI/规则推断先修、后继、相似等关系。"""
        all_kps = await self.knowledge.list_visible_by_course(
            course_id=course_id,
            current_user_id=owner_id,
            public_owner_id=None,
            include_all=True,
        )
        if len(all_kps) < 2:
            return 0

        kp_by_name = {kp.name.lower(): kp for kp in all_kps}
        relations = await self._llm_infer_relations(
            knowledge_points=all_kps,
            context_text=material_text[:6000],
            user_id=current_user.id,
            course_id=course_id,
        )
        if not relations:
            relations = self._rule_infer_material_relations(new_points, all_kps, material_text)

        return await self._persist_relations(
            current_user=current_user,
            course_id=course_id,
            relations=relations,
            kp_by_name=kp_by_name,
        )

    async def extract_from_dialogue_text(
        self,
        *,
        current_user: User,
        course_id: UUID,
        dialogue_text: str,
    ) -> dict[str, Any]:
        """规则 + 可选 LLM；无 Key 时用启发式抽取保证可演示。"""
        entities, relations = self._rule_extract(dialogue_text)
        if not entities:
            return {"entities_merged": 0, "relations_merged": 0, "created_entities": 0}

        try:
            from app.agents.knowledge_graph_agent import KnowledgeGraphAgent

            agent = KnowledgeGraphAgent(db=self.db)
            from app.agents.context import AgentContext

            result = await agent.run(
                AgentContext(
                    user_id=current_user.id,
                    course_id=course_id,
                    task_type="extract_knowledge_graph",
                    params={"dialogue_text": dialogue_text},
                )
            )
            if result.success and result.data.get("entities"):
                entities = result.data["entities"]
                relations = result.data.get("relations") or relations
        except Exception:
            pass

        return await self.merge_dialogue_extraction(
            current_user=current_user,
            course_id=course_id,
            entities=entities,
            relations=relations,
            dialogue_excerpt=dialogue_text[:500],
        )

    async def _ensure_wiki_for_knowledge(
        self,
        *,
        current_user: User,
        course_id: UUID,
        point: Any,
        draft: str,
        dialogue_excerpt: str,
    ) -> Any | None:
        existing_pages, _ = await self.wiki.list_visible_pages(
            current_user=current_user,
            course_id=course_id,
            status="active",
            page=1,
            page_size=200,
        )
        for page in existing_pages:
            if page.knowledge_id == point.id or page.title == point.name:
                if dialogue_excerpt and page.owner_id == current_user.id:
                    note = f"\n\n## 对话沉淀\n{dialogue_excerpt[:800]}\n"
                    if note.strip() not in page.content:
                        page.content = page.content + note
                        await self.db.flush()
                return None

        slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", point.name.lower())[:200] or "knowledge"
        content = draft or f"# {point.name}\n\n来自学习对话自动沉淀。\n"
        if dialogue_excerpt:
            content += f"\n## 对话摘录\n{dialogue_excerpt[:1000]}\n"
        page = await self.wiki.create_page(
            current_user=current_user,
            course_id=course_id,
            title=point.name,
            content=content,
            summary=draft[:200] if draft else None,
        )
        page.knowledge_id = point.id
        await self.db.flush()
        return page

    async def _mirror_wiki_link(
        self,
        *,
        current_user: User,
        course_id: UUID,
        source_kp: Any,
        target_kp: Any,
        relation_type: str,
        evidence: str,
    ) -> None:
        source_page = await self._find_page_for_kp(current_user, course_id, source_kp)
        target_page = await self._find_page_for_kp(current_user, course_id, target_kp)
        if not source_page or not target_page:
            return
        await self.wiki_repo.create_link(
            source_page_id=source_page.id,
            target_page_id=target_page.id,
            relation_type=relation_type,
            extra_meta={"evidence": evidence, "confidence": 0.75, "is_inferred": True},
        )

    async def _find_page_for_kp(self, user: User, course_id: UUID, kp: Any) -> Any | None:
        pages, _ = await self.wiki.list_visible_pages(
            current_user=user,
            course_id=course_id,
            status="active",
            page=1,
            page_size=200,
        )
        for page in pages:
            if page.knowledge_id == kp.id or page.title == kp.name:
                return page
        return None

    async def _knowledge_name_index(self, *, course_id: UUID, owner_id: UUID) -> dict[str, Any]:
        points = await self.knowledge.list_visible_by_course(
            course_id=course_id,
            current_user_id=owner_id,
            public_owner_id=None,
            include_all=True,
        )
        return {point.name.lower(): point for point in points}

    async def _persist_relations(
        self,
        *,
        current_user: User,
        course_id: UUID,
        relations: list[dict[str, Any]],
        kp_by_name: dict[str, Any],
    ) -> int:
        created_relations = 0
        for raw in relations:
            src_name = str(raw.get("source") or raw.get("source_name") or "").strip().lower()
            tgt_name = str(raw.get("target") or raw.get("target_name") or "").strip().lower()
            rel_type = str(raw.get("relation_type") or "related").strip()
            if not src_name or not tgt_name:
                continue
            src = kp_by_name.get(src_name)
            tgt = kp_by_name.get(tgt_name)
            if not src or not tgt or src.id == tgt.id:
                continue
            _, is_new = await self.relations.upsert(
                course_id=course_id,
                source_knowledge_id=src.id,
                target_knowledge_id=tgt.id,
                relation_type=rel_type,
                scope="personal",
                evidence=str(raw.get("evidence") or "")[:500] or None,
                confidence=float(raw.get("confidence") or 0.75),
                created_by="ai",
            )
            if is_new:
                created_relations += 1
            await self._mirror_wiki_link(
                current_user=current_user,
                course_id=course_id,
                source_kp=src,
                target_kp=tgt,
                relation_type=rel_type,
                evidence=str(raw.get("evidence") or ""),
            )
        return created_relations

    async def _llm_infer_relations(
        self,
        *,
        knowledge_points: list[Any],
        context_text: str,
        user_id: UUID,
        course_id: UUID,
    ) -> list[dict[str, Any]]:
        if len(knowledge_points) < 2:
            return []
        names = [kp.name for kp in knowledge_points[:80]]
        llm = get_llm_provider(db=self.db, user_id=user_id, course_id=course_id)
        prompt = (
            "你是数据结构课程知识图谱编辑。根据资料内容与已有知识点列表，推断知识点之间的关系。\n"
            "只返回 JSON：\n"
            '{"relations":[{"source":"知识点A","target":"知识点B",'
            '"relation_type":"prerequisite|next|similar|used_in|confused_with",'
            '"evidence":"一句依据","confidence":0.8}]}\n'
            "规则：\n"
            "- prerequisite：A 是 B 的前置知识，用单向箭头 A→B\n"
            "- next：A 学完后建议学 B\n"
            "- similar / confused_with：易混或并列，可双向\n"
            "- used_in：A 应用于 B（如队列 used_in BFS）\n"
            "只输出有明确依据的关系，不要编造。\n\n"
            f"已有知识点：{json.dumps(names, ensure_ascii=False)}\n\n"
            f"资料摘录：\n{context_text[:4500]}"
        )
        try:
            response = await llm.chat(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.2,
                max_tokens=2048,
            )
            data = self._parse_json(response.content)
            if isinstance(data, dict) and isinstance(data.get("relations"), list):
                return [item for item in data["relations"] if isinstance(item, dict)]
        except Exception:
            pass
        return []

    def _rule_infer_material_relations(
        self,
        new_points: list[Any],
        all_points: list[Any],
        material_text: str,
    ) -> list[dict[str, Any]]:
        relations: list[dict[str, Any]] = []
        by_chapter: dict[str, list[Any]] = {}
        for point in all_points:
            chapter = str(point.chapter or "通用").strip()
            by_chapter.setdefault(chapter, []).append(point)

        for chapter, points in by_chapter.items():
            ordered = sorted(points, key=lambda p: (p.sort_order, p.name))
            for idx in range(len(ordered) - 1):
                relations.append(
                    {
                        "source": ordered[idx].name,
                        "target": ordered[idx + 1].name,
                        "relation_type": "next",
                        "evidence": f"同章节「{chapter}」学习顺序推断",
                        "confidence": 0.55,
                    }
                )

        pairs = [
            ("栈", "队列", "similar"),
            ("队列", "BFS", "used_in"),
            ("链表", "线性表", "belongs_to"),
            ("二叉树", "树", "belongs_to"),
        ]
        names_in_text = {p.name for p in all_points}
        for src, tgt, rel_type in pairs:
            if src in names_in_text and tgt in names_in_text:
                relations.append(
                    {
                        "source": src,
                        "target": tgt,
                        "relation_type": rel_type,
                        "evidence": "课程常见知识结构关联",
                        "confidence": 0.6,
                    }
                )

        if "栈" in material_text and "队列" in material_text:
            relations.append(
                {
                    "source": "栈",
                    "target": "队列",
                    "relation_type": "similar",
                    "evidence": "资料中同时讲解栈与队列",
                    "confidence": 0.65,
                }
            )
        return relations

    def _parse_json(self, text: str) -> object:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _rule_extract(self, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        terms = [
            "栈", "队列", "链表", "二叉树", "图", "BFS", "DFS", "排序", "哈希表",
            "递归", "动态规划", "堆", "树", "数组", "复杂度",
        ]
        found = [t for t in terms if t in text]
        entities = [{"name": t, "description": f"对话中提及：{t}"} for t in found]
        relations: list[dict[str, Any]] = []
        if "栈" in found and "队列" in found:
            relations.append(
                {
                    "source": "栈",
                    "target": "队列",
                    "relation_type": "similar",
                    "evidence": "同一对话中对比栈与队列",
                }
            )
        if "BFS" in found and "队列" in found:
            relations.append(
                {
                    "source": "队列",
                    "target": "BFS",
                    "relation_type": "used_in",
                    "evidence": "BFS 通常使用队列",
                }
            )
        return entities, relations
