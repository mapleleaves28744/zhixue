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
    public_kb = _public_kb_summary(source_root)
    pipeline_stages = _pipeline_stages(
        raw_file_count=raw_file_count,
        normalized_document_count=len(normalized_files),
        source_traceability_rate=_ratio(len(source_traced_files), len(normalized_files)),
        public_kb=public_kb,
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
        "public_kb": public_kb,
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


def _public_kb_summary(source_root: Path) -> dict[str, Any]:
    report_path = source_root / "eval" / "public_kb_eval_report.json"
    if not report_path.exists():
        return {}
    import json

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {
        "course_id": payload.get("course_id"),
        "course_code": payload.get("course_code"),
        "course_visibility": payload.get("course_visibility"),
        "corpus_stats": payload.get("corpus_stats") or {},
        "embedding": payload.get("embedding") or {},
        "indexes": payload.get("indexes") or [],
        "metrics": payload.get("metrics") or {},
        "llm_sample_count": len(payload.get("llm_answers") or []),
        "real_llm_sample_count": sum(
            1
            for item in payload.get("llm_answers") or []
            if item.get("success")
            and item.get("provider") not in {None, "mock", "fallback"}
            and item.get("fallback_used") is False
        ),
    }


def _pipeline_stages(
    *,
    raw_file_count: int,
    normalized_document_count: int,
    source_traceability_rate: float,
    public_kb: dict[str, Any],
) -> list[dict[str, str]]:
    has_documents = raw_file_count > 0 or normalized_document_count > 0
    has_normalized = normalized_document_count > 0
    traceable = source_traceability_rate > 0
    corpus_stats = public_kb.get("corpus_stats") or {}
    embedding = public_kb.get("embedding") or {}
    metrics = public_kb.get("metrics") or {}
    indexes = set(public_kb.get("indexes") or [])
    chunk_count = int(corpus_stats.get("chunks") or 0)
    embedded_count = int(corpus_stats.get("embedded_chunks") or 0)
    embedding_ready = chunk_count > 0 and embedded_count == chunk_count
    required_indexes = {
        "idx_document_chunks_embedding_hnsw",
        "idx_document_chunks_content_trgm",
        "idx_document_chunks_extra_meta_gin",
    }
    indexing_ready = required_indexes.issubset(indexes)
    retrieval_ready = int(metrics.get("question_count") or 0) > 0
    real_llm_ready = int(public_kb.get("real_llm_sample_count") or 0) > 0
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
            "status": "ready" if embedding_ready else ("ready_for_build" if has_normalized else "missing"),
            "evidence": (
                f"{embedded_count}/{chunk_count} chunks 已使用 "
                f"{embedding.get('provider', 'unknown')} / {embedding.get('model', 'unknown')} / "
                f"{embedding.get('dimension', 'unknown')} 维真实向量化；"
                f"allow_mock_fallback={embedding.get('allow_mock_fallback')}。"
                if embedding_ready
                else "build_data_structure_kb.py 调用 EmbeddingService；尚未发现完整真实入库评测证据。"
            ),
            "next_action": "保持模型、维度和 pgvector 字段一致；更换模型时重新构建和评测。",
        },
        {
            "stage_id": "indexing",
            "name": "索引",
            "status": "ready" if indexing_ready else ("partial" if has_normalized else "missing"),
            "evidence": (
                "pgvector HNSW、内容 pg_trgm 关键词索引和 extra_meta GIN 元数据索引均已建立。"
                if indexing_ready
                else "尚未发现 pgvector HNSW、内容 pg_trgm 与 extra_meta GIN 三类索引的完整评测证据。"
            ),
            "next_action": "持续用 EXPLAIN ANALYZE 观察查询计划；数据量增大后调优索引参数。",
        },
        {
            "stage_id": "retrieval",
            "name": "检索",
            "status": "ready" if retrieval_ready else ("ready_for_query_after_build" if has_normalized else "missing"),
            "evidence": (
                f"HybridRetriever 已完成向量、关键词、metadata 混合检索；"
                f"{metrics.get('question_count')} 个标准问题检索召回率 {float(metrics.get('retrieval_recall') or 0):.0%}。"
                if retrieval_ready
                else "POST /api/v1/knowledge/search 使用 HybridRetriever，并带课程/用户可见性校验。"
            ),
            "next_action": "持续记录漏召回问题并优化切片、关键词权重和来源多样性。",
        },
        {
            "stage_id": "rerank",
            "name": "Rerank",
            "status": "ready" if retrieval_ready else "planned",
            "evidence": (
                "HybridRetriever 已执行向量分数、关键词分数、metadata 与来源多样性的轻量规则 rerank。"
                if retrieval_ready
                else "尚未发现混合检索评测证据。"
            ),
            "next_action": "Phase 5 可在规则 rerank 后增加 cross-encoder/LLM rerank。",
        },
        {
            "stage_id": "llm_answer",
            "name": "LLM 回答",
            "status": "ready" if real_llm_ready else ("ready_for_query_after_build" if has_normalized else "missing"),
            "evidence": (
                f"已通过真实 LLM 完成 {public_kb.get('real_llm_sample_count')} 个 RAG 样例回答，fallback_used=false。"
                if real_llm_ready
                else "Tutor/Wiki/Resource Agent 已接入检索片段；尚未发现真实 LLM 样例评测证据。"
            ),
            "next_action": "扩大真实 LLM 抽样规模，并持续审查回答依据。",
        },
        {
            "stage_id": "citations",
            "name": "引用来源",
            "status": "ready" if retrieval_ready and float(metrics.get("citation_rate") or 0) > 0 else ("ready_for_query_after_build" if has_normalized else "missing"),
            "evidence": (
                f"标准问题评测引用率 {float(metrics.get('citation_rate') or 0):.0%}；Tutor 输出可追溯 citations。"
                if retrieval_ready
                else "Tutor/Resource 输出 citations；WikiSource 记录 source_type/source_id/quote_text。"
            ),
            "next_action": "PDF/网页导入时继续补页码、URL fragment、段落定位。",
        },
        {
            "stage_id": "feedback_optimization",
            "name": "反馈优化",
            "status": "ready" if retrieval_ready else "partial",
            "evidence": (
                f"已生成标准问题逐题命中记录；回答准确率 {float(metrics.get('answer_accuracy') or 0):.0%}，"
                f"幻觉率 {float(metrics.get('hallucination_rate') or 0):.0%}。"
                if retrieval_ready
                else "已有 Tutor/推荐反馈表；尚未生成知识库标准问题评测记录。"
            ),
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
    public_kb = report.get("public_kb") or {}
    corpus_stats = public_kb.get("corpus_stats") or {}
    embedding = public_kb.get("embedding") or {}
    metrics = public_kb.get("metrics") or {}
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
- 公有课程：{public_kb.get('course_code', 'not_built')} / {public_kb.get('course_visibility', 'unknown')}
- 实际入库：{corpus_stats.get('materials', 0)} 份资料 / {corpus_stats.get('chunks', 0)} chunks / {corpus_stats.get('embedded_chunks', 0)} embeddings / {corpus_stats.get('knowledge_points', 0)} 知识点
- Embedding：{embedding.get('provider', 'unknown')} / {embedding.get('model', 'unknown')} / {embedding.get('dimension', 'unknown')} 维 / allow_mock_fallback={embedding.get('allow_mock_fallback', 'unknown')}
- 标准问题检索召回率：{float(metrics.get('retrieval_recall') or 0):.0%}
- 标准问题回答准确率：{float(metrics.get('answer_accuracy') or 0):.0%}
- 标准问题幻觉率：{float(metrics.get('hallucination_rate') or 0):.0%}
- 标准问题引用率：{float(metrics.get('citation_rate') or 0):.0%}

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
