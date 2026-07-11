from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.course_kb_common import read_yaml
from scripts.evaluate_public_kb import calculate_metrics


def test_metrics_do_not_infer_answer_correctness_from_retrieval_hit() -> None:
    metrics = calculate_metrics(
        [
            {
                "answerable": True,
                "expected_sources": ["source-a"],
                "retrieved_source_ids": ["source-a", "source-b"],
                "cited_source_ids": ["source-b"],
                "answer_correct": None,
                "refused": False,
                "llm_evaluated": True,
            },
            {
                "answerable": False,
                "expected_sources": [],
                "retrieved_source_ids": [],
                "cited_source_ids": [],
                "answer_correct": True,
                "refused": True,
                "llm_evaluated": True,
            },
        ]
    )

    assert metrics["recall_at_5"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["citation_precision"] == 0.0
    assert metrics["citation_coverage"] == 0.0
    assert metrics["unanswerable_refusal_rate"] == 1.0
    assert metrics["answer_correctness"] == 1.0
    assert metrics["manually_scored_answers"] == 1


def test_citation_precision_requires_expected_source_and_evidence_term() -> None:
    metrics = calculate_metrics(
        [
            {
                "answerable": True,
                "expected_sources": ["source-a"],
                "expected_evidence_terms": ["路径压缩"],
                "retrieved_source_ids": ["source-a"],
                "cited_source_ids": ["source-a", "source-a", "source-b"],
                "cited_quotes": ["并查集使用路径压缩。", "只有并查集。", "路径压缩。"],
                "answer_correct": None,
                "refused": False,
                "llm_evaluated": True,
            }
        ]
    )

    assert metrics["citation_precision"] == 0.3333
    assert metrics["citation_coverage"] == 1.0
    assert metrics["answer_correctness"] is None
    assert metrics["manually_scored_answers"] == 0


def test_citation_requires_every_evidence_term_group() -> None:
    metrics = calculate_metrics(
        [
            {
                "answerable": True,
                "expected_sources": ["source-a"],
                "expected_evidence_terms": ["B 树", ["B+ 树", "B 加树"], "外存"],
                "retrieved_source_ids": ["source-a"],
                "cited_source_ids": ["source-a", "source-a"],
                "cited_quotes": ["B 树适合索引。", "B 树和 B+ 树通过降低外存访问次数支持索引。"],
                "answer_correct": None,
                "refused": False,
                "llm_evaluated": True,
            }
        ]
    )

    assert metrics["citation_precision"] == 0.5
    assert metrics["citation_coverage"] == 1.0


def test_standard_questions_include_evidence_terms_and_interference_cases() -> None:
    source_root = Path(__file__).resolve().parents[2]
    payload = read_yaml(
        source_root / "data" / "seed_knowledge" / "data_structure" / "eval" / "standard_questions.yml"
    )
    questions = payload["questions"]

    assert len(questions) == 33
    assert all(item.get("expected_evidence_terms") for item in questions if item["answerable"])
    assert sum(item["answerable"] is False for item in questions) == 3
