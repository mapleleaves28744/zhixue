#!/usr/bin/env python3
"""Sequentially rebuild only legacy low-quality Wiki pages from course materials."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT if BACKEND_ROOT.exists() else PROJECT_ROOT))

from app.db.session import AsyncSessionLocal, async_engine
from app.services.wiki_generate_service import WikiGenerateService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id", required=True, type=UUID)
    parser.add_argument("--owner-id", required=True, type=UUID)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> list[dict[str, object]]:
    async with AsyncSessionLocal() as db:
        return await WikiGenerateService(db).rebuild_low_quality_pages(
            course_id=args.course_id,
            owner_id=args.owner_id,
            limit=args.limit,
            dry_run=args.dry_run,
        )


async def run_and_close(args: argparse.Namespace) -> list[dict[str, object]]:
    try:
        return await run(args)
    finally:
        await async_engine.dispose()


def main() -> None:
    args = parse_args()
    results = asyncio.run(run_and_close(args))
    summary: dict[str, int] = {}
    for result in results:
        status = str(result.get("status", "unknown"))
        summary[status] = summary.get(status, 0) + 1
    print(json.dumps({"summary": summary, "pages": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
