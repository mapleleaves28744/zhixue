import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_agent_runtime import score_scenario, summarize
from scripts.evaluate_public_kb import _evaluation_citations


def _task(status: str, tools: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(), status=status,
        plan_json={"tool_calls": [{"name": name} for name in tools]},
        iteration_count=1, tool_call_count=0, replan_count=0, error_message=None,
    )


def test_planned_and_failed_tools_do_not_count_as_successful_execution() -> None:
    scenario = {
        "id": "multi", "goal": "检索并出题", "category": "multi_agent",
        "expected_tool_groups": [["search_course_knowledge"], ["generate_quiz"]],
    }
    steps = [
        SimpleNamespace(action="search_course_knowledge", status="succeeded"),
        SimpleNamespace(action="generate_quiz", status="failed"),
    ]

    result = score_scenario(scenario, _task("succeeded", ["search_course_knowledge", "generate_quiz"]), steps, [])

    assert result["passed"] is False
    assert result["actual_tools"] == ["search_course_knowledge"]
    assert result["attempted_tools"] == ["search_course_knowledge", "generate_quiz"]
    assert summarize([result])["tool_selection_accuracy"] == 0.0


def test_waiting_confirmation_counts_plan_only_if_tool_was_not_attempted() -> None:
    scenario = {
        "id": "risk", "goal": "应用策略", "category": "high_risk",
        "expected_any_tools": ["apply_evolution_strategy"],
        "expected_statuses": ["waiting_confirmation"],
    }
    task = _task("waiting_confirmation", ["apply_evolution_strategy"])

    assert score_scenario(scenario, task, [], [])["passed"] is True
    attempted = [SimpleNamespace(action="apply_evolution_strategy", status="failed")]
    assert score_scenario(scenario, task, attempted, [])["passed"] is False


def test_unmeasured_security_metrics_are_not_reported_as_zero() -> None:
    summary = summarize([])
    assert summary["duplicate_write_count"] is None
    assert summary["cross_user_leak_count"] is None


def test_timeout_stays_in_tool_selection_denominator() -> None:
    summary = summarize([{
        "status": "timeout", "passed": False,
        "expected_any_tools": ["generate_explanation"],
        "tool_match": False,
    }])
    assert summary["tool_selection_accuracy"] == 0.0


def test_unresolved_citation_remains_in_precision_denominator() -> None:
    result = SimpleNamespace(chunk_id="known", extra_meta={"source_id": "source-a"})
    sources, quotes = _evaluation_citations(
        [{"chunk_id": "unknown", "source_id": "source-a", "quote": "quoted"}], [result]
    )
    assert sources == [""]
    assert quotes == ["quoted"]


def test_successful_task_with_mock_text_is_not_real_model_acceptance() -> None:
    scenario = {"id": "fallback", "goal": "讲解栈", "expected_any_tools": ["generate_explanation"]}
    step = SimpleNamespace(action="generate_explanation", status="succeeded", output_payload={"model_name": "mock-learning-model"})
    result = score_scenario(scenario, _task("succeeded", ["generate_explanation"]), [step], [])
    assert not result["passed"]
    assert result["mock_text_fallback_tools"] == ["generate_explanation"]
