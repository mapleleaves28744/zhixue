"""Import seed knowledge graph YAML into knowledge_points + knowledge_relations."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

from scripts.course_kb_common import read_yaml

from app.db.session import AsyncSessionLocal
from app.models.course import Course
from app.repositories.knowledge_relation_repository import KnowledgeRelationRepository
from app.repositories.knowledge_repository import KnowledgeRepository


async def import_graph(*, course_id: UUID, owner_id: UUID, graph_dir: Path) -> dict:
    entities = (read_yaml(graph_dir / "entities.yml") or {}).get("entities") or []
    relations = (read_yaml(graph_dir / "relations.yml") or {}).get("relations") or []

    async with AsyncSessionLocal() as db:
        course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
        if course is None:
            raise RuntimeError(f"course not found: {course_id}")

        kp_repo = KnowledgeRepository(db)
        rel_repo = KnowledgeRelationRepository(db)
        entity_map: dict[str, UUID] = {}
        created_kp = 0
        created_rel = 0

        for item in entities:
            entity_id = str(item.get("entity_id") or "")
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            point, is_new = await kp_repo.create_if_not_exists(
                course_id=course_id,
                owner_id=owner_id,
                scope="public",
                name=name,
                chapter=str(item.get("chapter_id") or "")[:128] or None,
                description=str(item.get("entity_type") or "")[:128] or None,
                sort_order=len(entity_map),
            )
            if entity_id:
                entity_map[entity_id] = point.id
            entity_map[name] = point.id
            if is_new:
                created_kp += 1

        for item in relations:
            src_key = str(item.get("source_id") or item.get("source") or "")
            tgt_key = str(item.get("target_id") or item.get("target") or "")
            src_id = entity_map.get(src_key)
            tgt_id = entity_map.get(tgt_key)
            if not src_id or not tgt_id:
                continue
            _, is_new = await rel_repo.upsert(
                course_id=course_id,
                source_knowledge_id=src_id,
                target_knowledge_id=tgt_id,
                relation_type=str(item.get("relation_type") or "related"),
                scope="public",
                evidence=str(item.get("evidence") or "")[:500] or None,
                confidence=1.0,
                created_by="seed",
            )
            if is_new:
                created_rel += 1

        await db.commit()
        return {
            "course_id": str(course_id),
            "entities": len(entities),
            "relations": len(relations),
            "created_knowledge_points": created_kp,
            "created_relations": created_rel,
        }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import seed knowledge graph")
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument(
        "--graph-dir",
        default=str(REPO_ROOT / "data" / "seed_knowledge" / "data_structure" / "graph"),
    )
    args = parser.parse_args()
    result = await import_graph(
        course_id=UUID(args.course_id),
        owner_id=UUID(args.owner_id),
        graph_dir=Path(args.graph_dir),
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
