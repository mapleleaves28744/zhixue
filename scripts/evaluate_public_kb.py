from __future__ import annotations

import argparse
import asyncio
import json
import sys
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
    if question_count == 0:
        return {
            "question_count": 0,
            "retrieval_recall": 0.0,
            "answer_accuracy": 0.0,
            "hallucination_rate": 0.0,
            "citation_rate": 0.0,
        }
    retrieval_hits = sum(1 for row in rows if _source_hit(row))
    grounded_answers = sum(1 for row in rows if row.get("answer_grounded"))
    hallucinations = sum(1 for row in rows if not row.get("answer_grounded"))
    cited = sum(1 for row in rows if row.get("answer_has_citation"))
    return {
        "question_count": question_count,
        "retrieval_recall": round(retrieval_hits / question_count, 4),
        "answer_accuracy": round(grounded_answers / question_count, 4),
        "hallucination_rate": round(hallucinations / question_count, 4),
        "citation_rate": round(cited / question_count, 4),
    }


async def evaluate_public_kb(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    course_id: UUID | None = None,
    top_k: int = 8,
    run_llm_sample: int = 0,
) -> dict[str, Any]:
    from sqlalchemy import select, text

    from app.agents.context import AgentContext
    from app.agents.tutor_agent import TutorAgent
    from app.core.config import settings
    from app.db.session import AsyncSessionLocal
    from app.models.course import Course
    from app.rag.hybrid_retriever import HybridRetriever

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
            expected_sources = list(item.get("expected_sources") or [])
            results = await retriever.search(
                course_id=course.id,
                query=question,
                user_id=course.owner_id,
                top_k=top_k,
            )
            retrieved_source_ids = [
                str(result.extra_meta.get("source_id"))
                for result in results
                if result.extra_meta.get("source_id")
            ]
            source_hit = bool(set(expected_sources).intersection(retrieved_source_ids))
            answer_has_citation = bool(results)
            row = {
                "question": question,
                "expected_sources": expected_sources,
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
                "answer_has_citation": answer_has_citation,
                "answer_grounded": source_hit and answer_has_citation,
            }
            rows.append(row)

            if index < run_llm_sample:
                agent_result = await TutorAgent(db).run(
                    AgentContext(
                        user_id=course.owner_id,
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
                llm_answers.append(
                    {
                        "question": question,
                        "success": agent_result.success,
                        "answer": agent_result.data.get("answer"),
                        "citations": agent_result.data.get("citations") or [],
                        "provider": agent_result.data.get("provider"),
                        "fallback_used": agent_result.data.get("fallback_used"),
                    }
                )

    metrics = calculate_metrics(rows)
    report = {
        "course_id": str(course.id),
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
    eval_dir = source_root / "eval"
    write_json(eval_dir / "public_kb_eval_report.json", report)
    (eval_dir / "public_kb_eval_report.md").write_text(_markdown_report(report), encoding="utf-8")
    return report


def _source_hit(row: dict[str, Any]) -> bool:
    return bool(set(row.get("expected_sources") or []).intersection(row.get("retrieved_source_ids") or []))


def _load_questions(source_root: Path) -> list[dict[str, Any]]:
    payload = read_yaml(source_root / "eval" / "standard_questions.yml")
    questions = payload.get("questions", []) if isinstance(payload, dict) else []
    return [item for item in questions if isinstance(item, dict) and item.get("question")]


def _markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    answer_lines = "\n".join(
        f"- {item['question']}：provider={item.get('provider')}, fallback={item.get('fallback_used')}, citations={len(item.get('citations') or [])}"
        for item in report.get("llm_answers", [])
    ) or "- 未运行 LLM 样例回答"
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
- 检索召回率：{metrics['retrieval_recall']:.0%}
- 回答准确率：{metrics['answer_accuracy']:.0%}
- 幻觉率：{metrics['hallucination_rate']:.0%}
- 引用率：{metrics['citation_rate']:.0%}

## 索引

{chr(10).join(f"- {name}" for name in report.get('indexes', []))}

## RAG 样例回答

{answer_lines}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the public Data Structure KB.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--course-id")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--run-llm-sample", type=int, default=0)
    args = parser.parse_args()

    report = asyncio.run(
        evaluate_public_kb(
            source_root=args.source_root,
            course_id=UUID(args.course_id) if args.course_id else None,
            top_k=args.top_k,
            run_llm_sample=args.run_llm_sample,
        )
    )
    metrics = report["metrics"]
    print(f"course_id: {report['course_id']}")
    print(f"retrieval_recall: {metrics['retrieval_recall']}")
    print(f"answer_accuracy: {metrics['answer_accuracy']}")
    print(f"hallucination_rate: {metrics['hallucination_rate']}")


if __name__ == "__main__":
    main()
