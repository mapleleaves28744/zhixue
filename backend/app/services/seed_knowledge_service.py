from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import PROJECT_ROOT
from app.models.chunk import DocumentChunk
from app.models.knowledge import KnowledgePoint
from app.models.material import CourseMaterial
from app.models.wiki import WikiLink, WikiPage
from app.services.wiki_service import describe_wiki_page_quality


DEFAULT_DATA_STRUCTURE_ROOT = PROJECT_ROOT / "data" / "seed_knowledge" / "data_structure"


def load_seed_quality_report(source_root: Path = DEFAULT_DATA_STRUCTURE_ROOT) -> dict[str, Any]:
    report_path = source_root / "eval" / "quality_report.json"
    manifest_path = source_root / "sources_manifest.yml"
    report = _read_json(report_path)
    manifest = _read_yaml(manifest_path)
    sources = manifest.get("sources", []) if isinstance(manifest, dict) else []
    return {
        "source_root": str(source_root),
        "report": report,
        "sources": [
            {
                "source_id": source.get("source_id"),
                "name": source.get("name"),
                "license": source.get("license"),
                "import_status": source.get("import_status"),
                "review_status": source.get("review_status"),
                "risk_level": source.get("risk_level"),
                "quality_score": source.get("quality_score"),
            }
            for source in sources
            if isinstance(source, dict)
        ],
    }


async def load_course_quality_report(db: AsyncSession, *, course_id: UUID) -> dict[str, Any]:
    """Build the quality report from the selected course, not from optional seed files."""
    material_count = int(
        (await db.scalar(select(func.count()).select_from(CourseMaterial).where(CourseMaterial.course_id == course_id)))
        or 0
    )
    parsed_material_count = int(
        (
            await db.scalar(
                select(func.count())
                .select_from(CourseMaterial)
                .where(CourseMaterial.course_id == course_id, CourseMaterial.parse_status == "success")
            )
        )
        or 0
    )
    chunk_count = int(
        (await db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.course_id == course_id)))
        or 0
    )
    knowledge_point_count = int(
        (await db.scalar(select(func.count()).select_from(KnowledgePoint).where(KnowledgePoint.course_id == course_id)))
        or 0
    )
    pages = list(
        (
            await db.execute(
                select(WikiPage)
                .options(selectinload(WikiPage.sources))
                .where(WikiPage.course_id == course_id, WikiPage.status == "active")
            )
        ).scalars().all()
    )
    wiki_link_count = int(
        (
            await db.scalar(
                select(func.count())
                .select_from(WikiLink)
                .join(WikiPage, WikiPage.id == WikiLink.source_page_id)
                .where(WikiPage.course_id == course_id)
            )
        )
        or 0
    )
    qualities = [describe_wiki_page_quality(page) for page in pages]
    metrics = {
        "material_count": material_count,
        "parsed_material_count": parsed_material_count,
        "chunk_count": chunk_count,
        "knowledge_point_count": knowledge_point_count,
        "wiki_page_count": len(pages),
        "sourced_wiki_page_count": sum(quality["source_count"] > 0 for quality in qualities),
        "qualified_wiki_page_count": sum(quality["status"] == "verified" for quality in qualities),
        "wiki_source_count": sum(int(quality["source_count"]) for quality in qualities),
        "wiki_link_count": wiki_link_count,
    }
    return {
        "source_root": None,
        "report": build_runtime_course_report(course_id=str(course_id), metrics=metrics),
        "sources": [],
    }


def build_runtime_course_report(*, course_id: str, metrics: dict[str, int]) -> dict[str, Any]:
    material_count = int(metrics.get("material_count", 0))
    parsed_material_count = int(metrics.get("parsed_material_count", 0))
    chunk_count = int(metrics.get("chunk_count", 0))
    knowledge_point_count = int(metrics.get("knowledge_point_count", 0))
    wiki_page_count = int(metrics.get("wiki_page_count", 0))
    sourced_wiki_page_count = int(metrics.get("sourced_wiki_page_count", 0))
    qualified_wiki_page_count = int(metrics.get("qualified_wiki_page_count", 0))
    wiki_source_count = int(metrics.get("wiki_source_count", 0))
    wiki_link_count = int(metrics.get("wiki_link_count", 0))
    source_coverage_rate = round(sourced_wiki_page_count / wiki_page_count, 3) if wiki_page_count else 0.0
    graphrag_ready = bool(material_count and chunk_count and qualified_wiki_page_count and wiki_link_count)

    def stage(status: str, stage_id: str, name: str, evidence: str, next_action: str) -> dict[str, str]:
        return {
            "stage_id": stage_id,
            "name": name,
            "status": status,
            "evidence": evidence,
            "next_action": next_action,
        }

    return {
        "report_scope": "course_runtime",
        "course_id": course_id,
        "raw_document_count": material_count,
        "normalized_document_count": parsed_material_count,
        "chunk_count": chunk_count,
        "knowledge_point_count": knowledge_point_count,
        "wiki": {
            "page_count": wiki_page_count,
            "sourced_page_count": sourced_wiki_page_count,
            "qualified_page_count": qualified_wiki_page_count,
            "source_count": wiki_source_count,
            "link_count": wiki_link_count,
            "source_coverage_rate": source_coverage_rate,
        },
        "pipeline_stages": [
            stage("ready" if material_count else "missing", "materials", "课程资料", f"当前课程有 {material_count} 份资料。", "上传或选择课程资料。"),
            stage("ready" if parsed_material_count else "missing", "parsing", "解析与规范化", f"已成功解析 {parsed_material_count}/{material_count} 份资料。", "先完成资料解析，再进入切片。"),
            stage("ready" if chunk_count else "missing", "chunking", "知识切片", f"当前课程已有 {chunk_count} 个可检索切片。", "执行切片和向量化。"),
            stage("ready" if knowledge_point_count else "partial", "knowledge", "知识点抽取", f"当前课程已有 {knowledge_point_count} 个知识点。", "从已解析资料抽取并归并知识点。"),
            stage("ready" if qualified_wiki_page_count else "partial", "wiki", "Wiki 内容质量", f"{qualified_wiki_page_count}/{wiki_page_count} 个页面达到已核验标准。", "优先补强无来源或正文过短的页面。"),
            stage("ready" if wiki_link_count else "partial", "graph", "知识图谱", f"当前课程已有 {wiki_link_count} 条页面关系。", "补全页面关联后再查看图谱。"),
        ],
        "graphrag_ready": graphrag_ready,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "graphrag_ready": False,
            "message": "quality_report.json 尚未生成，请先运行 scripts/evaluate_course_kb.py",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}
