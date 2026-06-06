from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.build_data_structure_kb import build_to_database
from scripts.course_kb_common import DEFAULT_SOURCE_ROOT


PUBLIC_OWNER_USERNAME = "public_kb_owner"
PUBLIC_COURSE_CODE = "DS-PUBLIC"


def public_course_payload() -> dict[str, str]:
    return {
        "title": "数据结构",
        "course_code": PUBLIC_COURSE_CODE,
        "description": "面向所有用户开放的《数据结构》公共课程知识库。",
        "subject": "计算机科学",
        "visibility": "public_template",
        "status": "active",
    }


async def ensure_public_data_structure_kb(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    rebuild: bool = False,
    use_mock_embedding: bool = False,
    require_real_embedding: bool = False,
) -> dict[str, Any]:
    if require_real_embedding and not _has_embedding_key():
        raise RuntimeError(
            "require_real_embedding is enabled, but EMBEDDING_API_KEY/OPENAI_EMBEDDING_API_KEY/LLM_API_KEY is missing."
        )
    if use_mock_embedding:
        os.environ["EMBEDDING_PROVIDER"] = "mock"

    from sqlalchemy import delete, select

    from app.core.security import hash_password
    from app.db.session import AsyncSessionLocal
    from app.models.course import Course
    from app.models.knowledge import KnowledgePoint
    from app.models.material import CourseMaterial
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        owner = (
            await db.execute(select(User).where(User.username == PUBLIC_OWNER_USERNAME))
        ).scalar_one_or_none()
        if owner is None:
            owner = User(
                username=PUBLIC_OWNER_USERNAME,
                email=None,
                password_hash=hash_password("public-kb-owner-local-only"),
                role="admin",
                status="active",
            )
            db.add(owner)
            await db.flush()
            await db.refresh(owner)

        payload = public_course_payload()
        course = (
            await db.execute(select(Course).where(Course.course_code == PUBLIC_COURSE_CODE))
        ).scalar_one_or_none()
        if course is None:
            course = Course(
                owner_id=owner.id,
                title=payload["title"],
                course_code=payload["course_code"],
                description=payload["description"],
                subject=payload["subject"],
                visibility=payload["visibility"],
                status=payload["status"],
            )
            db.add(course)
            await db.flush()
            await db.refresh(course)
        else:
            course.owner_id = owner.id
            course.title = payload["title"]
            course.description = payload["description"]
            course.subject = payload["subject"]
            course.visibility = payload["visibility"]
            course.status = payload["status"]
            await db.flush()
            await db.refresh(course)

        if rebuild:
            await db.execute(
                delete(CourseMaterial).where(
                    CourseMaterial.course_id == course.id,
                    CourseMaterial.uploaded_by == owner.id,
                )
            )
            await db.execute(
                delete(KnowledgePoint).where(
                    KnowledgePoint.course_id == course.id,
                    KnowledgePoint.owner_id == owner.id,
                )
            )
            await db.flush()
        await db.commit()
        owner_id = owner.id
        course_id = course.id

    result = await build_to_database(
        source_root=source_root,
        course_id=course_id,
        user_id=owner_id,
        rebuild=False,
        use_mock_embedding=use_mock_embedding,
    )
    return {
        "course_id": str(course_id),
        "owner_id": str(owner_id),
        "visibility": public_course_payload()["visibility"],
        **result,
    }


def _has_embedding_key() -> bool:
    return bool(
        os.getenv("EMBEDDING_API_KEY")
        or os.getenv("OPENAI_EMBEDDING_API_KEY")
        or os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the public Data Structure KB.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--use-mock-embedding", action="store_true")
    parser.add_argument("--require-real-embedding", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(
        ensure_public_data_structure_kb(
            source_root=args.source_root,
            rebuild=args.rebuild,
            use_mock_embedding=args.use_mock_embedding,
            require_real_embedding=args.require_real_embedding,
        )
    )
    print(f"course_id: {result['course_id']}")
    print(f"owner_id: {result['owner_id']}")
    print(f"visibility: {result['visibility']}")
    print(f"imported: {result['imported']}")
    print(f"skipped: {result['skipped']}")


if __name__ == "__main__":
    main()
