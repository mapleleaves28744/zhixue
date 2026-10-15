from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.course_kb_common import DEFAULT_SOURCE_ROOT, read_yaml, write_json
from scripts.init_public_data_structure_kb import PUBLIC_COURSE_CODE


def calculate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    question_count = len(rows)
    answerable_rows = [row for row in rows if row.get("answerable") is True]
    answerable_count = len(answerable_rows)
    recall_hits = sum(1 for row in answerable_rows if _source_hit(row, limit=5))
    reciprocal_rank_sum = sum(_reciprocal_rank(row, limit=5) for row in answerable_rows)

    evaluated_rows = [row for row in rows if row.get("llm_evaluated") is True]
    llm_evaluated_count = len(evaluated_rows)
    cited_count = sum(len(row.get("cited_source_ids") or []) for row in evaluated_rows)
    valid_citations = sum(_valid_citation_count(row) for row in evaluated_rows)
    answerable_evaluated_rows = [row for row in evaluated_rows if row.get("answerable") is True]
    covered_answers = sum(1 for row in answerable_evaluated_rows if _citation_covers_evidence(row))

    unanswerable_rows = [row for row in evaluated_rows if row.get("answerable") is False]
    reviewed_refusals = [row for row in unanswerable_rows if row.get("refusal_reviewed") is True]
    refusals = sum(1 for row in reviewed_refusals if row.get("refused") is True)

    scored_rows = [row for row in rows if isinstance(row.get("answer_correct"), bool)]
    scored_count = len(scored_rows)
    correct = sum(1 for row in scored_rows if row["answer_correct"] is True)
    return {
        "question_count": question_count,
        "answerable_questions": answerable_count,
        "recall_at_5": round(recall_hits / answerable_count, 4) if answerable_count else None,
        "mrr": round(reciprocal_rank_sum / answerable_count, 4) if answerable_count else None,
        "citation_precision": (
            round(valid_citations / cited_count, 4)
            if cited_count
            else (0.0 if llm_evaluated_count else None)
        ),
        "citation_coverage": (
            round(covered_answers / len(answerable_evaluated_rows), 4)
            if answerable_evaluated_rows
            else None
        ),
        "unanswerable_refusal_rate": (
            round(refusals / len(reviewed_refusals), 4) if reviewed_refusals else None
        ),
        "unanswerable_reviewed_answers": len(reviewed_refusals),
        "unanswerable_insufficient_rate": (
            round(
                sum(row.get("grounding_status") == "insufficient" for row in unanswerable_rows)
                / len(unanswerable_rows),
                4,
            )
            if unanswerable_rows
            else None
        ),
        "answer_correctness": round(correct / scored_count, 4) if scored_count else None,
        "llm_evaluated_answers": llm_evaluated_count,
        "manually_scored_answers": scored_count,
    }


async def evaluate_public_kb(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    course_id: UUID | None = None,
    user_id: UUID | None = None,
    top_k: int = 8,
    run_llm_sample: int = 0,
    require_real_provider: bool = False,
    expected_model: str | None = None,
    output_prefix: Path | None = None,
) -> dict[str, Any]:
    from app.agents.context import AgentContext
    from app.agents.tutor_agent import TutorAgent
    from app.core.config import settings
    from app.db.session import AsyncSessionLocal
    from app.models.course import Course
    from app.models.user import User
    from app.rag.hybrid_retriever import HybridRetriever
    from sqlalchemy import select, text

    if require_real_provider and (
        settings.llm_provider not in {"compatible", "openai_compatible"}
        or not settings.llm_api_key
        or run_llm_sample <= 0
    ):
        raise ValueError("真实回答评测要求 OpenAI-compatible Provider、API Key 和正数采样量")
    if expected_model and settings.llm_model_name != expected_model:
        raise ValueError(f"模型不匹配：配置为 {settings.llm_model_name}，预期 {expected_model}")

    questions = _load_questions(source_root)
    rows: list[dict[str, Any]] = []
    llm_answers: list[dict[str, Any]] = []
    corpus_stats: dict[str, int] = {}
    index_names: list[str] = []
    async with AsyncSessionLocal() as db:
        course = None
        if course_id is not None:
            course = await db.get(Course, course_id)
        if course is None:
            course = (
                await db.execute(select(Course).where(Course.course_code == PUBLIC_COURSE_CODE))
            ).scalar_one_or_none()
        if course is None:
            raise RuntimeError("Public Data Structure course not found. Run init_public_data_structure_kb.py first.")
        evaluation_user = await db.get(User, user_id or course.owner_id)
        if evaluation_user is None:
            raise ValueError(f"评测用户不存在: {user_id}")

        corpus_stats = dict(
            (
                await db.execute(
                    text(
                        """
                        select
                          (select count(*) from course_materials where course_id=:course_id) as materials,
                          (select count(*) from document_chunks where course_id=:course_id) as chunks,
                          (select count(*) from document_chunks where course_id=:course_id and embedding is not null) as embedded_chunks,
                          (select count(*) from knowledge_points where course_id=:course_id) as knowledge_points
                        """
                    ),
                    {"course_id": course.id},
                )
            ).mappings().one()
        )
        index_names = [
            row[0]
            for row in await db.execute(
                text(
                    """
                    select indexname
                    from pg_indexes
                    where tablename='document_chunks'
                    order by indexname
                    """
                )
            )
        ]
        retriever = HybridRetriever(db)
        for index, item in enumerate(questions):
            question = str(item["question"])
            answerable = item.get("answerable") is not False
            expected_sources = list(item.get("expected_sources") or [])
            expected_evidence_terms = list(item.get("expected_evidence_terms") or [])
            results = await retriever.search(
                course_id=course.id,
                query=question,
                user_id=evaluation_user.id,
                top_k=top_k,
            )
            retrieved_source_ids = [
                str(result.extra_meta.get("source_id"))
                for result in results
                if result.extra_meta.get("source_id")
            ]
            row = {
                "question": question,
                "answerable": answerable,
                "expected_sources": expected_sources,
                "expected_evidence_terms": expected_evidence_terms,
                "retrieved_source_ids": retrieved_source_ids,
                "top_chunks": [
                    {
                        "chunk_id": str(result.chunk_id),
                        "source_id": result.extra_meta.get("source_id"),
                        "source_title": result.source_title,
                        "score": round(result.score, 4),
                        "mode": result.retrieval_mode,
                    }
                    for result in results[:5]
                ],
                "llm_evaluated": False,
                "cited_source_ids": [],
                "cited_quotes": [],
                "refused": False,
                "refusal_reviewed": False,
                "answer_correct": None,
            }
            rows.append(row)

            if index < run_llm_sample:
                print(f"[public-kb {index + 1}/{min(run_llm_sample, len(questions))}] answering", flush=True)
                agent_result = await TutorAgent(db).run(
                    AgentContext(
                        user_id=evaluation_user.id,
                        course_id=course.id,
                        task_type="course_qa",
                        params={
                            "question": question,
                            "use_rag": True,
                            "use_wiki": False,
                            "use_profile": False,
                            "top_k": min(top_k, 6),
                        },
                    )
                )
                citations = list(agent_result.data.get("citations") or [])
                provider = agent_result.data.get("provider")
                model = agent_result.data.get("model")
                fallback_used = agent_result.data.get("fallback_used")
                if require_real_provider and (
                    not agent_result.success
                    or fallback_used
                    or not provider
                    or str(provider).lower() == "mock"
                    or model != settings.llm_model_name
                ):
                    raise RuntimeError(
                        f"第 {index + 1} 题未得到预期真实模型结果：provider={provider}, model={model}, fallback={fallback_used}"
                    )
                cited_source_ids, cited_quotes = _evaluation_citations(citations, results)
                grounding_status = str(agent_result.data.get("grounding_status") or "")
                refused = _is_refusal(str(agent_result.data.get("answer") or ""))
                row.update(
                    {
                        "llm_evaluated": True,
                        "cited_source_ids": cited_source_ids,
                        "cited_quotes": cited_quotes,
                        "refused": refused,
                        "refusal_reviewed": False,
                        "grounding_status": grounding_status,
                        "answer_correct": None,
                    }
                )
                llm_answers.append(
                    {
                        "question": question,
                        "success": agent_result.success,
                        "answer": agent_result.data.get("answer"),
                        "citations": citations,
                        "cited_source_ids": cited_source_ids,
                        "cited_quotes": cited_quotes,
                        "refused": refused,
                        "refusal_reviewed": False,
                        "grounding_status": grounding_status,
                        "answer_correct": None,
                        "provider": agent_result.data.get("provider"),
                        "model": model,
                        "fallback_used": agent_result.data.get("fallback_used"),
                    }
                )
                print(
                    f"[public-kb {index + 1}/{min(run_llm_sample, len(questions))}] "
                    f"provider={provider} model={model} fallback={fallback_used}",
                    flush=True,
                )

    metrics = calculate_metrics(rows)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model_name,
        "require_real_provider": require_real_provider,
        "course_id": str(course.id),
        "evaluation_user_id": str(evaluation_user.id),
        "course_code": course.course_code,
        "course_visibility": course.visibility,
        "top_k": top_k,
        "corpus_stats": corpus_stats,
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimension": settings.embedding_dimension,
            "allow_mock_fallback": settings.embedding_allow_mock_fallback,
        },
        "indexes": index_names,
        "metrics": metrics,
        "rows": rows,
        "llm_answers": llm_answers,
    }
    prefix = output_prefix or source_root / "eval" / "public_kb_eval_report"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    write_json(Path(f"{prefix}.json"), report)
    Path(f"{prefix}.md").write_text(_markdown_report(report), encoding="utf-8")
    return report


def _source_hit(row: dict[str, Any], *, limit: int | None = None) -> bool:
    retrieved = list(row.get("retrieved_source_ids") or [])
    if limit is not None:
        retrieved = retrieved[:limit]
    return bool(set(row.get("expected_sources") or []).intersection(retrieved))


def _is_refusal(answer: str) -> bool:
    if not answer.strip():
        return True
    return bool(re.search(
        r"无法(?:根据|从|回答|确认|判断)|不能(?:确定|回答|确认)|资料不足|依据不足|"
        r"未(?:提供|找到|收录)|没有足够|不包含|insufficient|cannot answer|can't answer",
        answer,
        flags=re.IGNORECASE,
    ))


def _reciprocal_rank(row: dict[str, Any], *, limit: int) -> float:
    expected = set(row.get("expected_sources") or [])
    for rank, source_id in enumerate((row.get("retrieved_source_ids") or [])[:limit], start=1):
        if source_id in expected:
            return 1.0 / rank
    return 0.0


def _valid_citation_count(row: dict[str, Any]) -> int:
    expected_sources = set(row.get("expected_sources") or [])
    evidence_term_groups = _evidence_term_groups(row.get("expected_evidence_terms") or [])
    cited_source_ids = list(row.get("cited_source_ids") or [])
    cited_quotes = list(row.get("cited_quotes") or [])
    valid = 0
    for index, source_id in enumerate(cited_source_ids):
        if source_id not in expected_sources:
            continue
        if evidence_term_groups:
            quote = str(cited_quotes[index] if index < len(cited_quotes) else "").casefold()
            if not any(any(term in quote for term in group) for group in evidence_term_groups):
                continue
        valid += 1
    return valid


def _citation_covers_evidence(row: dict[str, Any]) -> bool:
    expected_sources = set(row.get("expected_sources") or [])
    groups = _evidence_term_groups(row.get("expected_evidence_terms") or [])
    valid_quotes = [
        str(quote).casefold()
        for source, quote in zip(row.get("cited_source_ids") or [], row.get("cited_quotes") or [])
        if source in expected_sources
    ]
    if not valid_quotes:
        return False
    return all(any(term in quote for quote in valid_quotes for term in group) for group in groups)


def _evidence_term_groups(raw_terms: list[Any]) -> list[list[str]]:
    groups: list[list[str]] = []
    for raw_term in raw_terms:
        alternatives = raw_term if isinstance(raw_term, list) else [raw_term]
        normalized = [str(term).casefold() for term in alternatives if str(term).strip()]
        if normalized:
            groups.append(normalized)
    return groups


def _evaluation_citations(
    citations: list[dict[str, Any]],
    retrieval_results: list[Any],
) -> tuple[list[str], list[str]]:
    source_by_chunk = {
        str(result.chunk_id): str(result.extra_meta.get("source_id"))
        for result in retrieval_results
        if result.extra_meta.get("source_id")
    }
    source_ids: list[str] = []
    quotes: list[str] = []
    for citation in citations:
        chunk_id = citation.get("chunk_id")
        source_id = source_by_chunk.get(str(chunk_id)) if chunk_id else None
        source_ids.append(str(source_id or ""))
        quotes.append(str(citation.get("quote") or ""))
    return source_ids, quotes


def _load_questions(source_root: Path) -> list[dict[str, Any]]:
    payload = read_yaml(source_root / "eval" / "standard_questions.yml")
    questions = payload.get("questions", []) if isinstance(payload, dict) else []
    return [item for item in questions if isinstance(item, dict) and item.get("question")]


def _markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    answer_lines = "\n".join(
        f"- {item['question']}：provider={item.get('provider')}, fallback={item.get('fallback_used')}, citations={len(item.get('citations') or [])}"
        for item in report.get("llm_answers", [])
    ) or "- 未运行回答评测"
    correctness = (
        "未独立评分"
        if metrics["answer_correctness"] is None
        else f"{metrics['answer_correctness']:.0%}"
    )
    citation_precision = _format_metric(metrics["citation_precision"])
    citation_coverage = _format_metric(metrics["citation_coverage"])
    refusal_rate = _format_metric(metrics["unanswerable_refusal_rate"])
    return f"""# 公有《数据结构》知识库评测报告

## 总览

- course_id：{report['course_id']}
- course_code：{report['course_code']}
- visibility：{report['course_visibility']}
- 资料数：{report['corpus_stats']['materials']}
- chunks：{report['corpus_stats']['chunks']}
- 已向量化 chunks：{report['corpus_stats']['embedded_chunks']}
- 知识点数：{report['corpus_stats']['knowledge_points']}
- Embedding：{report['embedding']['provider']} / {report['embedding']['model']} / {report['embedding']['dimension']} 维
- 禁止 Mock fallback：{not report['embedding']['allow_mock_fallback']}
- 标准问题数：{metrics['question_count']}
- 可回答问题数：{metrics['answerable_questions']}
- Recall@5：{_format_metric(metrics['recall_at_5'])}
- MRR：{_format_metric(metrics['mrr'])}
- 引用精确率：{citation_precision}
- 引用覆盖率：{citation_coverage}
- 不可回答问题拒答率：{refusal_rate}
- 人工复核拒答题数：{metrics['unanswerable_reviewed_answers']}
- 不可回答题依据不足率：{_format_metric(metrics['unanswerable_insufficient_rate'])}
- 回答正确性：{correctness}
- 已运行回答评测：{metrics['llm_evaluated_answers']}
- 已独立评分回答：{metrics['manually_scored_answers']}

## 索引

{chr(10).join(f"- {name}" for name in report.get('indexes', []))}

## RAG 样例回答

{answer_lines}
"""


def _format_metric(value: float | None) -> str:
    return "未评测" if value is None else f"{value:.0%}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the public Data Structure KB.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--course-id")
    parser.add_argument("--user-id")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--run-llm-sample", type=int, default=0)
    parser.add_argument("--require-real-provider", action="store_true")
    parser.add_argument("--expected-model")
    parser.add_argument("--output-prefix", type=Path)
    args = parser.parse_args()

    report = asyncio.run(
        evaluate_public_kb(
            source_root=args.source_root,
            course_id=UUID(args.course_id) if args.course_id else None,
            user_id=UUID(args.user_id) if args.user_id else None,
            top_k=args.top_k,
            run_llm_sample=args.run_llm_sample,
            require_real_provider=args.require_real_provider,
            expected_model=args.expected_model,
            output_prefix=args.output_prefix,
        )
    )
    metrics = report["metrics"]
    print(f"course_id: {report['course_id']}")
    print(f"recall_at_5: {metrics['recall_at_5']}")
    print(f"mrr: {metrics['mrr']}")
    print(f"citation_precision: {metrics['citation_precision']}")
    print(f"citation_coverage: {metrics['citation_coverage']}")
    print(f"unanswerable_refusal_rate: {metrics['unanswerable_refusal_rate']}")
    print(f"answer_correctness: {metrics['answer_correctness']}")


if __name__ == "__main__":
    main()
