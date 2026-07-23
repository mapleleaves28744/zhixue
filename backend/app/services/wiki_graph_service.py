from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.knowledge_relation_repository import KnowledgeRelationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.course_service import CourseService
from app.services.mastery_service import MasteryService
from app.services.wiki_service import WikiService

BIDIRECTIONAL_RELATION_TYPES = frozenset({"similar", "confused_with", "related"})


class WikiGraphService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.wiki = WikiService(db)
        self.knowledge = KnowledgeRepository(db)
        self.relations = KnowledgeRelationRepository(db)
        self.mastery = MasteryService(db)

    async def get_graph(
        self,
        *,
        current_user: User,
        course_id: UUID,
        view: str = "personal",
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        course = await CourseService(self.db).get_course(course_id, current_user)
        public_owner_id = course.owner_id if course.visibility == "public_template" else None

        pages, _ = await self.wiki.list_visible_pages(
            current_user=current_user,
            course_id=course_id,
            status="active",
            page=1,
            page_size=500,
        )
        await self._bind_wiki_pages_to_knowledge(course_id=course_id, pages=pages)
        mastery_map = await self.mastery.get_mastery_map(
            user_id=current_user.id,
            course_id=course_id,
            apply_decay=True,
        )

        page_by_id = {p.id: p for p in pages}
        page_by_kp: dict[UUID, Any] = {}
        for p in pages:
            if p.knowledge_id:
                page_by_kp[p.knowledge_id] = p

        nodes: list[dict[str, Any]] = []
        for p in pages:
            is_personal = p.owner_id == current_user.id
            if view == "personal" and not is_personal:
                continue
            kp_id = str(p.knowledge_id) if p.knowledge_id else None
            nodes.append(
                {
                    "id": str(p.id),
                    "title": p.title,
                    "summary": p.summary,
                    "knowledge_id": kp_id,
                    "mastery_score": mastery_map.get(kp_id, MasteryService.INITIAL_MASTERY) if kp_id else MasteryService.INITIAL_MASTERY,
                    "mastery_confidence": 0.6 if kp_id in mastery_map else 0.2,
                    "scope": "personal" if is_personal else "shared",
                    "page_type": "wiki",
                    "current_version": p.current_version,
                }
            )

        visible_ids = {p.id for p in pages if view != "personal" or p.owner_id == current_user.id}
        links: list[dict[str, Any]] = []

        for p in pages:
            if p.id not in visible_ids:
                continue
            for link in await self.wiki.repo.list_links(p.id):
                if link.source_page_id not in visible_ids or link.target_page_id not in visible_ids:
                    continue
                meta = link.extra_meta or {}
                links.append(
                    self._format_link(
                        link_id=str(link.id),
                        source=str(link.source_page_id),
                        target=str(link.target_page_id),
                        relation_type=link.relation_type,
                        evidence=meta.get("evidence"),
                        confidence=float(meta.get("confidence", 1.0)),
                        is_inferred=bool(meta.get("is_inferred", False)),
                        scope="personal",
                        line_style="solid",
                    )
                )

        personal_kp_ids = {
            p.knowledge_id for p in pages if p.owner_id == current_user.id and p.knowledge_id
        }
        if personal_kp_ids and self.relations is not None:
            kp_edges = await self.relations.list_by_course(
                course_id,
                scopes=["personal"],
            )
            for edge in kp_edges:
                if edge.source_knowledge_id not in personal_kp_ids and edge.target_knowledge_id not in personal_kp_ids:
                    continue
                src_page = page_by_kp.get(edge.source_knowledge_id)
                tgt_page = page_by_kp.get(edge.target_knowledge_id)
                if not src_page or not tgt_page:
                    continue
                if src_page.id not in visible_ids or tgt_page.id not in visible_ids:
                    continue
                links.append(
                    self._format_link(
                        link_id=str(edge.id),
                        source=str(src_page.id),
                        target=str(tgt_page.id),
                        relation_type=edge.relation_type,
                        evidence=edge.evidence,
                        confidence=float(edge.confidence),
                        is_inferred=edge.created_by == "ai",
                        scope="personal",
                        line_style="solid",
                    )
                )

        if view == "merged":
            if personal_kp_ids:
                public_kps = await self.knowledge.list_visible_by_course(
                    course_id=course_id,
                    current_user_id=current_user.id,
                    public_owner_id=public_owner_id,
                )
                public_by_id = {kp.id: kp for kp in public_kps if kp.scope == "public"}
                neighbor_edges = await self.relations.expand_neighbors(
                    course_id,
                    list(personal_kp_ids),
                    hops=1,
                    scopes=["public"],
                )
                added_kp: set[UUID] = set()
                for edge in neighbor_edges:
                    for kp_id in (edge.source_knowledge_id, edge.target_knowledge_id):
                        if kp_id in personal_kp_ids or kp_id in added_kp:
                            continue
                        kp = public_by_id.get(kp_id)
                        if not kp:
                            continue
                        added_kp.add(kp_id)
                        wiki_page = page_by_kp.get(kp_id)
                        node_id = str(wiki_page.id) if wiki_page else f"kp:{kp_id}"
                        nodes.append(
                            {
                                "id": node_id,
                                "title": kp.name,
                                "summary": kp.description,
                                "knowledge_id": str(kp_id),
                                "mastery_score": mastery_map.get(str(kp_id), MasteryService.INITIAL_MASTERY),
                                "mastery_confidence": 0.6 if str(kp_id) in mastery_map else 0.2,
                                "scope": "public_neighbor",
                                "page_type": "knowledge",
                                "current_version": 0,
                            }
                        )

                    src_page = page_by_kp.get(edge.source_knowledge_id)
                    tgt_page = page_by_kp.get(edge.target_knowledge_id)
                    src_id = str(src_page.id) if src_page else f"kp:{edge.source_knowledge_id}"
                    tgt_id = str(tgt_page.id) if tgt_page else f"kp:{edge.target_knowledge_id}"
                    if any(n["id"] == src_id for n in nodes) and any(n["id"] == tgt_id for n in nodes):
                        links.append(
                            self._format_link(
                                link_id=str(edge.id),
                                source=src_id,
                                target=tgt_id,
                                relation_type=edge.relation_type,
                                evidence=edge.evidence,
                                confidence=float(edge.confidence),
                                is_inferred=edge.created_by == "ai",
                                scope="public",
                                line_style="dashed",
                            )
                        )

        seen: set[str] = set()
        unique_links: list[dict[str, Any]] = []
        for link in links:
            key = f"{link['source']}-{link['target']}-{link['relation_type']}"
            if key in seen:
                continue
            seen.add(key)
            unique_links.append(link)

        return {"nodes": nodes, "links": unique_links, "view": view}

    async def _bind_wiki_pages_to_knowledge(self, *, course_id: UUID, pages: list[Any]) -> None:
        if self.knowledge is None:
            return
        changed = False
        for page in pages:
            if page.knowledge_id:
                continue
            kp = await self.knowledge.find_by_course_and_name(
                course_id,
                page.owner_id,
                page.title,
            )
            if kp is None:
                continue
            page.knowledge_id = kp.id
            changed = True
        if changed:
            await self.db.flush()

    @staticmethod
    def _format_link(
        *,
        link_id: str,
        source: str,
        target: str,
        relation_type: str,
        evidence: str | None,
        confidence: float,
        is_inferred: bool,
        scope: str,
        line_style: str,
    ) -> dict[str, Any]:
        direction = "both" if relation_type in BIDIRECTIONAL_RELATION_TYPES else "forward"
        return {
            "id": link_id,
            "source": source,
            "target": target,
            "source_page_id": source,
            "target_page_id": target,
            "relation_type": relation_type,
            "evidence": evidence,
            "confidence": confidence,
            "is_inferred": is_inferred,
            "scope": scope,
            "line_style": line_style,
            "direction": direction,
        }

    async def get_subgraph(
        self,
        *,
        current_user: User,
        course_id: UUID,
        center_id: UUID,
        depth: int = 2,
    ) -> dict[str, Any]:
        graph = await self.get_graph(current_user=current_user, course_id=course_id, view="merged")
        node_ids = {n["id"] for n in graph["nodes"]}
        if str(center_id) not in node_ids:
            center_str = str(center_id)
            for n in graph["nodes"]:
                if n.get("knowledge_id") == center_str:
                    center_str = n["id"]
                    break
            else:
                center_str = str(center_id)
        else:
            center_str = str(center_id)

        frontier = {center_str}
        visited = {center_str}
        collected_links: list[dict[str, Any]] = []
        for _ in range(max(1, depth)):
            next_frontier: set[str] = set()
            for link in graph["links"]:
                src, tgt = link["source"], link["target"]
                if src in frontier or tgt in frontier:
                    collected_links.append(link)
                    for nid in (src, tgt):
                        if nid not in visited:
                            visited.add(nid)
                            next_frontier.add(nid)
            frontier = next_frontier

        nodes = [n for n in graph["nodes"] if n["id"] in visited]
        return {"nodes": nodes, "links": collected_links, "center_id": center_str}
