from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.course_kb_common import DEFAULT_SOURCE_ROOT, read_sources, read_yaml, write_json


def evaluate_seed_knowledge(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, Any]:
    course_outline = read_yaml(source_root / "course_outline.yml")
    chapters = course_outline.get("chapters", []) if isinstance(course_outline, dict) else []
    normalized_files = sorted((source_root / "normalized").glob("**/*.md"))
    source_traced_files = [
        path for path in normalized_files if _frontmatter(path).get("source_id")
    ]
    covered_chapters = {
        meta["chapter_id"]
        for meta in (_frontmatter(path) for path in normalized_files)
        if meta.get("chapter_id")
    }
    graph = _graph_counts(source_root)
    standard_questions = _standard_question_count(source_root)
    sources = read_sources(source_root)
    approved_sources = [
        source
        for source in sources
        if source.get("review_status") == "approved"
        and source.get("import_status") in {"approved_importable", "approved_link_only"}
    ]
    importable_sources = [
        source for source in approved_sources if source.get("import_status") == "approved_importable"
    ]
    relation_count = graph["relation_count"]
    entity_count = graph["entity_count"]
    claim_count = graph["claim_count"]
    raw_file_count = len(
        [
            path
            for path in (source_root / "raw").glob("**/*")
            if path.is_file() and path.name != ".gitkeep"
        ]
    )
    pipeline_stages = _pipeline_stages(
        raw_file_count=raw_file_count,
        normalized_document_count=len(normalized_files),
        source_traceability_rate=_ratio(len(source_traced_files), len(normalized_files)),
    )

    report = {
        "source_root": str(source_root),
        "raw_document_count": raw_file_count,
        "source_count": len(sources),
        "approved_source_count": len(approved_sources),
        "importable_source_count": len(importable_sources),
        "chapter_count": len(chapters),
        "covered_chapter_count": len(covered_chapters),
        "chapter_coverage_rate": _ratio(len(covered_chapters), len(chapters)),
        "normalized_document_count": len(normalized_files),
        "source_traceability_rate": _ratio(len(source_traced_files), len(normalized_files)),
        "standard_question_count": standard_questions,
        "graph": graph,
        "pipeline_stages": pipeline_stages,
        "pipeline_summary": _pipeline_summary(pipeline_stages),
        "graphrag_ready": bool(
            normalized_files and entity_count and relation_count and claim_count and standard_questions
        ),
    }
    return report


def write_quality_report(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, Any]:
    report = evaluate_seed_knowledge(source_root)
    eval_dir = source_root / "eval"
    write_json(eval_dir / "quality_report.json", report)
    (eval_dir / "quality_report.md").write_text(_report_markdown(report), encoding="utf-8")
    return report


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = read_yaml_from_text(parts[1])
    return data if isinstance(data, dict) else {}


def read_yaml_from_text(text: str) -> Any:
    import yaml

    return yaml.safe_load(text) or {}


def _graph_counts(source_root: Path) -> dict[str, int]:
    graph_root = source_root / "graph"
    entities = read_yaml(graph_root / "entities.yml")
    relations = read_yaml(graph_root / "relations.yml")
    claims = read_yaml(graph_root / "claims.yml")
    return {
        "entity_count": len(entities.get("entities", [])) if isinstance(entities, dict) else 0,
        "relation_count": len(relations.get("relations", [])) if isinstance(relations, dict) else 0,
        "claim_count": len(claims.get("claims", [])) if isinstance(claims, dict) else 0,
    }


def _standard_question_count(source_root: Path) -> int:
    questions = read_yaml(source_root / "eval" / "standard_questions.yml")
    return len(questions.get("questions", [])) if isinstance(questions, dict) else 0


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _pipeline_stages(
    *,
    raw_file_count: int,
    normalized_document_count: int,
    source_traceability_rate: float,
) -> list[dict[str, str]]:
    has_documents = raw_file_count > 0 or normalized_document_count > 0
    has_normalized = normalized_document_count > 0
    traceable = source_traceability_rate > 0
    return [
        {
            "stage_id": "raw_documents",
            "name": "原始文档",
            "status": "ready" if has_documents else "missing",
            "evidence": f"raw 文件 {raw_file_count} 份；normalized 文档 {normalized_document_count} 份。",
            "next_action": "继续补充权威资料下载清单，并保留 license/source_url。",
        },
        {
            "stage_id": "document_parsing",
            "name": "文档解析",
            "status": "ready" if has_normalized else "missing",
            "evidence": "ingest_course_materials.py 已支持 HTML/Markdown/RST/PDF 到 normalized Markdown。",
            "next_action": "后续可扩展 Word/Excel 解析并记录页码、表格坐标。",
        },
        {
            "stage_id": "cleaning_normalization",
            "name": "清洗与格式统一",
            "status": "ready" if has_normalized and traceable else "partial",
            "evidence": f"normalized docs: {normalized_document_count}; source traceability: {source_traceability_rate:.0%}",
            "next_action": "补充更严格的噪声去除、重复段落检测和表格/公式规范化。",
        },
        {
            "stage_id": "hierarchy_chunking",
            "name": "层级切片",
            "status": "ready" if has_normalized else "missing",
            "evidence": "backend/app/rag/chunking.py 保留 heading_path，并保护代码块。",
            "next_action": "构建入库时由 ChunkService 写入 source/chapter/heading/license metadata。",
        },
        {
            "stage_id": "embedding",
            "name": "Embedding",
            "status": "ready_for_build" if has_normalized else "missing",
            "evidence": "build_data_structure_kb.py 调用 EmbeddingService；--use-mock-embedding 可无 Key 演示。",
            "next_action": "执行非 dry-run 构建后生成 document_chunks.embedding。",
        },
        {
            "stage_id": "indexing",
            "name": "索引",
            "status": "partial" if has_normalized else "missing",
            "evidence": "当前 DB 支持向量检索与 extra_meta 元数据；关键词检索仍是文本兜底，未建正式关键词索引。",
            "next_action": "Phase 1.1 可补 PostgreSQL tsvector/BM25-like keyword index and hybrid score config。",
        },
        {
            "stage_id": "retrieval",
            "name": "检索",
            "status": "ready_for_query_after_build" if has_normalized else "missing",
            "evidence": "POST /api/v1/knowledge/search 使用 VectorRetriever，并带文本兜底与课程/用户可见性校验。",
            "next_action": "构建入库后用 standard_questions.yml 做来源命中率评测。",
        },
        {
            "stage_id": "rerank",
            "name": "Rerank",
            "status": "planned",
            "evidence": "Phase 1 暂无独立 reranker；当前按向量距离或文本分数排序。",
            "next_action": "Phase 1.1 可加 lightweight lexical rerank；Phase 5 可接 cross-encoder/LLM rerank。",
        },
        {
            "stage_id": "llm_answer",
            "name": "LLM 回答",
            "status": "ready_for_query_after_build" if has_normalized else "missing",
            "evidence": "Tutor/Wiki/Resource Agent 通过 LLM Provider 消费检索片段；Mock Provider 保证可演示。",
            "next_action": "用标准问题集验证回答是否严格基于来源。",
        },
        {
            "stage_id": "citations",
            "name": "引用来源",
            "status": "ready_for_query_after_build" if has_normalized else "missing",
            "evidence": "Tutor/Resource 输出 citations；WikiSource 记录 source_type/source_id/quote_text。",
            "next_action": "PDF/网页导入时继续补页码、URL fragment、段落定位。",
        },
        {
            "stage_id": "feedback_optimization",
            "name": "反馈优化",
            "status": "partial",
            "evidence": "已有 Tutor/推荐反馈表；知识库专用漏召回/错答评估闭环尚未完成。",
            "next_action": "记录标准问题的漏召回、错答和低质量引用，反哺 chunking/rerank/source review。",
        },
    ]


def _pipeline_summary(stages: list[dict[str, str]]) -> dict[str, int]:
    summary = {"ready": 0, "ready_for_build": 0, "ready_for_query_after_build": 0, "partial": 0, "planned": 0, "missing": 0}
    for stage in stages:
        status = stage.get("status", "missing")
        summary[status] = summary.get(status, 0) + 1
    return summary


def _report_markdown(report: dict[str, Any]) -> str:
    graph = report["graph"]
    pipeline_lines = "\n".join(
        f"- {stage['name']}：{stage['status']}；{stage['evidence']}"
        for stage in report.get("pipeline_stages", [])
    )
    return f"""# 数据结构 GraphRAG-ready 知识库质量报告

## 总览

- 原始文档：{report['raw_document_count']}
- 资料源数量：{report['source_count']}
- 已审核资料源：{report['approved_source_count']}
- 可导入资料源：{report['importable_source_count']}
- 章节覆盖：{report['covered_chapter_count']} / {report['chapter_count']} ({report['chapter_coverage_rate']:.0%})
- normalized 文档：{report['normalized_document_count']}
- 来源可追溯率：{report['source_traceability_rate']:.0%}
- 标准问题数：{report['standard_question_count']}

## GraphRAG-ready v0

- 实体数：{graph['entity_count']}
- 关系数：{graph['relation_count']}
- 声明数：{graph['claim_count']}
- 状态：{'ready' if report['graphrag_ready'] else 'needs_more_data'}

## 知识库流水线

{pipeline_lines}

> Phase 1 仅建设 GraphRAG-ready v0，不执行完整 Microsoft GraphRAG community summaries。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate data-structure seed knowledge quality.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    args = parser.parse_args()

    report = write_quality_report(args.source_root)
    print(f"quality_report: {args.source_root / 'eval' / 'quality_report.json'}")
    print(f"graphrag_ready: {report['graphrag_ready']}")


if __name__ == "__main__":
    main()
