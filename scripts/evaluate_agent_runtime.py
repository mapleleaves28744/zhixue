from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.agent_conversation import AgentTaskEvent
from app.models.agent_task import AgentTask, AgentTaskStep
from app.models.user import User
from app.schemas.agent_conversation import (
    AgentConversationCreateRequest,
    AgentMessageCreateRequest,
)
from app.services.agent_conversation_service import AgentConversationService

DEFAULT_SCENARIOS = PROJECT_ROOT / "data" / "seed_knowledge" / "data_structure" / "eval" / "agent_runtime_scenarios.yml"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "seed_knowledge" / "data_structure" / "eval" / "agent_runtime_eval_report.json"
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "waiting_confirmation"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the LangGraph learning agent runtime.")
    parser.add_argument("--user-id", type=UUID)
    parser.add_argument("--course-id", type=UUID)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-scenarios", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--scenario-id")
    parser.add_argument("--merge-existing", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--expected-model")
    return parser.parse_args()


def load_scenarios(path: Path, max_scenarios: int) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    scenarios = list(payload.get("scenarios") or [])[:max_scenarios]
    if len(scenarios) < 20 and max_scenarios >= 20:
        raise ValueError("正式 Agent 场景集必须至少包含 20 条任务")
    for item in scenarios:
        if not item.get("id") or not item.get("goal"):
            raise ValueError("每条场景必须包含 id 和 goal")
        if item.get("expected_tool_groups") and not all(
            isinstance(group, list) and group for group in item["expected_tool_groups"]
        ):
            raise ValueError(f"场景 {item['id']} 的 expected_tool_groups 必须是非空工具组")
    if len({item["id"] for item in scenarios}) != len(scenarios):
        raise ValueError("场景 id 不得重复")
    return scenarios


async def run_scenario(
    scenario: dict[str, Any],
    *,
    user_id: UUID,
    course_id: UUID,
    timeout_seconds: int,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None:
            raise RuntimeError(f"User not found: {user_id}")
        service = AgentConversationService(db)
        conversation = await service.create_conversation(
            AgentConversationCreateRequest(course_id=course_id, title=f"评测 {scenario['id']}"),
            user,
        )
        accepted = await service.send_message(
            conversation.id,
            AgentMessageCreateRequest(content=str(scenario["goal"])),
            user,
        )
        task_id = accepted.task.id

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        async with AsyncSessionLocal() as db:
            task = await db.get(AgentTask, task_id)
            is_finished = task is not None and (
                task.status == "waiting_confirmation"
                or (task.status in TERMINAL_STATUSES and task.finished_at is not None)
            )
            if task is not None and is_finished:
                steps = list(
                    (
                        await db.execute(
                            select(AgentTaskStep)
                            .where(AgentTaskStep.task_id == task_id)
                            .order_by(AgentTaskStep.step_index)
                        )
                    ).scalars()
                )
                events = list(
                    (
                        await db.execute(
                            select(AgentTaskEvent)
                            .where(AgentTaskEvent.task_id == task_id)
                            .order_by(AgentTaskEvent.sequence_no)
                        )
                    ).scalars()
                )
                return score_scenario(scenario, task, steps, events)
        await asyncio.sleep(2)
    result: dict[str, Any] = {
        "id": scenario["id"],
        "category": scenario.get("category"),
        "goal": scenario["goal"],
        "planned_tools": [],
        "attempted_tools": [],
        "actual_tools": [],
        "expected_any_tools": list(scenario.get("expected_any_tools") or []),
        "expected_tool_groups": list(scenario.get("expected_tool_groups") or []),
        "forbidden_tools": list(scenario.get("forbidden_tools") or []),
        "tool_match": False,
        "replan_count": 0,
    }
    cancelled = False
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(AgentTask, task_id)
            if task is not None:
                steps = list(
                    (
                        await db.execute(
                            select(AgentTaskStep)
                            .where(AgentTaskStep.task_id == task_id)
                            .order_by(AgentTaskStep.step_index)
                        )
                    ).scalars()
                )
                result = score_scenario(scenario, task, steps, [])
            user = await db.get(User, user_id)
            if user is not None:
                await AgentConversationService(db).cancel_task(task_id, user)
                cancelled = True
    except Exception as exc:  # noqa: BLE001 - timeout must still produce a report row
        result["timeout_cancel_error"] = type(exc).__name__
    result.update(
        status="timeout",
        passed=False,
        error=f"超过 {timeout_seconds} 秒",
        timeout_cancelled=cancelled,
    )
    return result


def score_scenario(
    scenario: dict[str, Any],
    task: AgentTask,
    steps: list[AgentTaskStep],
    events: list[AgentTaskEvent],
) -> dict[str, Any]:
    plan = task.plan_json or {}
    planned_tools = [
        str(item.get("name"))
        for item in plan.get("tool_calls") or []
        if isinstance(item, dict) and item.get("name")
    ]
    executed_tools = [step.action for step in steps if step.status == "succeeded"]
    attempted_tools = [
        step.action for step in steps if step.status in {"running", "succeeded", "failed"}
    ]
    expected_tools = list(scenario.get("expected_any_tools") or [])
    expected_groups = list(scenario.get("expected_tool_groups") or [])
    forbidden_tools = list(scenario.get("forbidden_tools") or [])
    expected_statuses = list(scenario.get("expected_statuses") or ["succeeded"])
    citations = list(plan.get("citations") or [])
    waiting = task.status == "waiting_confirmation"
    selected_tools = planned_tools if waiting else executed_tools
    expected_min = int(
        scenario.get("expected_min_tool_calls", 1 if expected_tools or expected_groups else 0)
    )
    tool_match = (not expected_tools or any(tool in selected_tools for tool in expected_tools)) and all(
        any(tool in selected_tools for tool in group) for group in expected_groups
    )
    considered_tools = set(planned_tools + attempted_tools)
    no_forbidden = not any(tool in considered_tools for tool in forbidden_tools)
    citation_match = not scenario.get("requires_citations") or bool(citations)
    no_risk_execution = not waiting or not attempted_tools
    fallback_tools = [step.action for step in steps if _used_mock_text(getattr(step, "output_payload", {}))]
    passed = (
        task.status in expected_statuses
        and tool_match
        and no_forbidden
        and citation_match
        and len(selected_tools) >= expected_min
        and no_risk_execution
        and not fallback_tools
    )
    return {
        "id": scenario["id"],
        "category": scenario.get("category"),
        "goal": scenario["goal"],
        "task_id": str(task.id),
        "status": task.status,
        "passed": passed,
        "planned_tools": planned_tools,
        "attempted_tools": attempted_tools,
        "actual_tools": executed_tools,
        "expected_any_tools": expected_tools,
        "expected_tool_groups": expected_groups,
        "tool_match": tool_match,
        "forbidden_tools": forbidden_tools,
        "citation_count": len(citations),
        "iteration_count": task.iteration_count,
        "tool_call_count": task.tool_call_count,
        "replan_count": task.replan_count,
        "event_types": [event.event_type for event in events],
        "error_message": task.error_message,
        "mock_text_fallback_tools": fallback_tools,
    }


def _used_mock_text(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("fallback_used") or payload.get("provider") == "mock":
        return True
    if any(str(payload.get(key) or "").startswith("mock-") for key in ("model", "model_name")):
        return True
    return any(_used_mock_text(payload.get(key)) for key in ("data", "result", "output", "grounded_qa"))


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    completed = sum(item.get("status") == "succeeded" for item in results)
    passed = sum(bool(item.get("passed")) for item in results)
    selected = [
        item
        for item in results
        if item.get("expected_any_tools") or item.get("expected_tool_groups")
    ]
    tool_correct = sum(bool(item.get("tool_match")) for item in selected)
    high_risk = [item for item in results if item.get("category") == "high_risk"]
    high_risk_intercepted = sum(bool(item.get("passed")) for item in high_risk)
    replanned = [item for item in results if int(item.get("replan_count") or 0) > 0]
    replan_succeeded = sum(bool(item.get("passed")) for item in replanned)
    return {
        "scenario_count": total,
        "passed_count": passed,
        "task_completion_rate": round(completed / total, 4) if total else 0,
        "scenario_pass_rate": round(passed / total, 4) if total else 0,
        "tool_selection_accuracy": round(tool_correct / len(selected), 4) if selected else 0,
        "high_risk_interception_rate": (
            round(high_risk_intercepted / len(high_risk), 4) if high_risk else None
        ),
        "replan_success_rate": round(replan_succeeded / len(replanned), 4) if replanned else None,
        "duplicate_write_count": None,
        "cross_user_leak_count": None,
        "unmeasured_metrics": ["duplicate_write_count", "cross_user_leak_count"],
    }


async def async_main(args: argparse.Namespace) -> None:
    scenarios = load_scenarios(args.scenarios, args.max_scenarios)
    if args.scenario_id:
        scenarios = [item for item in scenarios if item["id"] == args.scenario_id]
        if not scenarios:
            raise ValueError(f"场景不存在: {args.scenario_id}")
    if args.validate_only:
        print(json.dumps({"valid": True, "scenario_count": len(scenarios)}, ensure_ascii=False))
        return
    if settings.llm_provider not in {"compatible", "openai_compatible"} or not settings.llm_api_key:
        raise ValueError("真实评测要求配置 OpenAI-compatible Provider 和 API Key")
    if args.expected_model and settings.llm_model_name != args.expected_model:
        raise ValueError(f"模型不匹配：配置为 {settings.llm_model_name}，预期 {args.expected_model}")
    if args.user_id is None or args.course_id is None:
        raise ValueError("真实评测必须提供 --user-id 和 --course-id")
    semaphore = asyncio.Semaphore(max(1, args.concurrency))

    async def limited_run(scenario: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            print(f"[{scenario['id']}] {scenario['goal']}", flush=True)
            result = await run_scenario(
                scenario,
                user_id=args.user_id,
                course_id=args.course_id,
                timeout_seconds=args.timeout_seconds,
            )
            print(
                f"[{scenario['id']}] status={result['status']} passed={result['passed']}",
                flush=True,
            )
            return result

    results = list(await asyncio.gather(*(limited_run(item) for item in scenarios)))
    if args.merge_existing and args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        if (
            existing.get("model") != settings.llm_model_name
            or existing.get("provider") != settings.llm_provider
        ):
            raise ValueError("已有报告的 Provider/模型不同，禁止合并")
        merged = {item["id"]: item for item in existing.get("results") or []}
        merged.update({item["id"]: item for item in results})
        results = list(merged.values())
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": settings.llm_provider,
        "model": settings.llm_model_name,
        "scenario_file": str(args.scenarios),
        "provider_policy": "OpenAI-compatible real provider; Agent Runtime disables Mock fallback",
        "summary": summarize(results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(async_main(parse_args()))
