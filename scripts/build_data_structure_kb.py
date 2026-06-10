from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.course_kb_common import DEFAULT_SOURCE_ROOT, read_yaml, sha256_text
from scripts.evaluate_course_kb import write_quality_report


def build_plan(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, Any]:
    normalized_files = sorted((source_root / "normalized").glob("**/*.md"))
    manifest = read_yaml(source_root / "sources_manifest.yml")
    sources = manifest.get("sources", []) if isinstance(manifest, dict) else []
    hashes = [_file_hash(path) for path in normalized_files]
    duplicate_hashes = sorted({value for value in hashes if hashes.count(value) > 1})
    return {
        "source_root": str(source_root),
        "normalized_document_count": len(normalized_files),
        "source_count": len(sources),
        "duplicate_hash_count": len(duplicate_hashes),
        "documents": [
            {
                "path": str(path.relative_to(source_root)),
                "text_hash": _file_hash(path),
                "size": path.stat().st_size,
            }
            for path in normalized_files
        ],
    }


async def build_to_database(
    *,
    source_root: Path,
    course_id: UUID,
    user_id: UUID,
    rebuild: bool = False,
    use_mock_embedding: bool = False,
) -> dict[str, Any]:
    backend_root = Path(__file__).resolve().parents[1] / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    if use_mock_embedding:
        import os

        os.environ["EMBEDDING_PROVIDER"] = "mock"

    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.course import Course
    from app.repositories.material_repository import MaterialRepository
    from app.services.chunk_service import ChunkService
    from app.services.embedding_service import EmbeddingService
    from app.services.knowledge_service import KnowledgeService

    normalized_files = sorted((source_root / "normalized").glob("**/*.md"))
    source_reviews = _source_review_map(source_root)
    imported = 0
    skipped = 0
    async with AsyncSessionLocal() as db:
        course = await db.get(Course, course_id)
        if course is None:
            raise RuntimeError(f"Course not found: {course_id}")
        if course.owner_id != user_id:
            raise RuntimeError("Seed import user_id must match course owner_id for Phase 1.")

        materials = MaterialRepository(db)
        existing_hashes = {
            value
            for value in (
                await db.execute(
                    select(materials._course_statement(course_id).subquery().c.text_hash)
                )
            ).scalars()
            if value
        }

        for path in normalized_files:
            text = path.read_text(encoding="utf-8")
            text_hash = sha256_text(text)
            if text_hash in existing_hashes and not rebuild:
                skipped += 1
                continue
            material = await materials.create(
                material_id=uuid4(),
                course_id=course_id,
                uploaded_by=user_id,
                file_name=path.name,
                file_type="md",
                file_size=path.stat().st_size,
                storage_path=str(path),
            )
            metadata = _frontmatter(text)
            source_review = source_reviews.get(str(metadata.get("source_id") or ""), {})
            material.parse_status = "success"
            material.text_hash = text_hash
            material.extra_meta = json_safe_metadata({
                **metadata,
                "source_quality_score": source_review.get("quality_score"),
                "source_risk_level": source_review.get("risk_level"),
                "source_review_status": source_review.get("review_status"),
                "parsed_text_path": str(path),
                "text_length": len(text),
                "seed_source_root": str(source_root),
            })
            await db.commit()
            await db.refresh(material)
            await ChunkService(db).chunk_material(material)
            await EmbeddingService(db).generate_embeddings(material.id)
            await KnowledgeService(db).extract_from_material(material.id)
            imported += 1

    report = write_quality_report(source_root)
    return {
        "imported": imported,
        "skipped": skipped,
        "quality_report": report,
    }


def _file_hash(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8", errors="ignore"))


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    import yaml

    data = yaml.safe_load(parts[1]) or {}
    return data if isinstance(data, dict) else {}


def json_safe_metadata(value: Any) -> Any:
    from datetime import date, datetime
    from uuid import UUID

    if isinstance(value, dict):
        return {str(key): json_safe_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe_metadata(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _source_review_map(source_root: Path) -> dict[str, dict[str, Any]]:
    manifest = read_yaml(source_root / "sources_manifest.yml")
    sources = manifest.get("sources", []) if isinstance(manifest, dict) else []
    return {
        str(source.get("source_id")): source
        for source in sources
        if isinstance(source, dict) and source.get("source_id")
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Data Structure seed knowledge base.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--course-id")
    parser.add_argument("--user-id")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--use-mock-embedding", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        plan = build_plan(args.source_root)
        print(f"normalized_document_count: {plan['normalized_document_count']}")
        print(f"source_count: {plan['source_count']}")
        print(f"duplicate_hash_count: {plan['duplicate_hash_count']}")
        return

    if not args.course_id or not args.user_id:
        raise SystemExit("Non-dry-run import requires --course-id and --user-id.")

    result = asyncio.run(
        build_to_database(
            source_root=args.source_root,
            course_id=UUID(args.course_id),
            user_id=UUID(args.user_id),
            rebuild=args.rebuild,
            use_mock_embedding=args.use_mock_embedding,
        )
    )
    print(f"imported: {result['imported']}")
    print(f"skipped: {result['skipped']}")


if __name__ == "__main__":
    main()
