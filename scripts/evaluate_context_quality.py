"""Frozen synthetic labels, paired context ablation and honest real-provider usage.

This measures contract parsing and synthetic fact retention, not teaching quality.
Each result is append-only; a completed case is never replaced by a better retry.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.agent_runtime.intent_contract import build_intent_frame, follow_up_topic
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider
from app.llm.schemas import ChatMessage
from app.services.conversation_context_service import ConversationContext
from app.services.intent_understanding_service import IntentUnderstandingService, needs_semantic_understanding
from evaluation_budget import BudgetProvider, EvaluationLedger, BudgetExceeded

BASE = ROOT / "data/seed_knowledge/data_structure/eval/quality_v1"
TOOLS = ["generate_quiz", "generate_explanation", "generate_mindmap", "generate_diagram"]
TOPICS = ["栈", "队列", "链表", "二叉树", "哈希表", "归并排序", "快速排序", "堆"]
# Template families, not merely examples, are disjoint between development and holdout.
TEMPLATES = {
    "dev": {
        "quiz": "给{a}出练习题", "explanation": "为{a}生成讲解资源",
        "multi": "{a}和{b}各出练习题", "answer": "{a}的原理是什么？",
        "followup": "再给我五道同类题", "clarify": "再给我五道同类题",
    },
    "holdout": {
        "quiz": "帮我准备一套关于{a}的自测题，并附上答案解析",
        "explanation": "替我写一份面向初学者的{a}讲解资源",
        "multi": "请给{a}出练习题，另外给{b}出练习题，分开交付",
        "answer": "学习{a}时，最容易混淆的概念是什么？",
        "followup": "继续围绕刚才那个知识点出练习题",
        "clarify": "帮我准备几道练习题，但我还没选定知识点",
    },
}


def make_dataset() -> dict:
    cases = []
    for split, patterns in TEMPLATES.items():
        for index, topic in enumerate(TOPICS):
            other = TOPICS[(index + 1) % len(TOPICS)]
            for kind, pattern in patterns.items():
                mode = "clarify" if kind == "clarify" else "answer" if kind == "answer" else "execute"
                names = [] if mode != "execute" else ["generate_explanation" if kind == "explanation" else "generate_quiz"]
                cases.append({"id": f"{split}-{kind}-{index:02}", "split": split, "kind": kind,
                              "goal": pattern.format(a=topic, b=other),
                              "previous": f"给{topic}出练习题" if kind == "followup" else None,
                              "mode": mode, "tasks": [[t, names] for t in ([topic, other] if kind == "multi" else [topic])] if names else []})
    return {"version": "quality-v1", "label_source": "automatic synthetic template labels",
            "independent_human_review": False, "split_unit": "template family",
            "purpose": "contract parsing, not delivery success or natural user distribution",
            "cases": cases}


def freeze_dataset(path: Path) -> dict:
    generated = make_dataset()
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != generated:
            raise ValueError("Frozen dataset differs; create a new version instead of changing labels")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(generated, handle, ensure_ascii=False, indent=2)
    return generated


def score_contract(case: dict, predicted: dict) -> bool:
    predicted = normalize_contract(predicted)
    actual = sorted((str(task["topic"]).strip(), tuple(sorted(task["tools"]))) for task in predicted.get("tasks", []))
    wanted = sorted((topic, tuple(sorted(names))) for topic, names in case["tasks"])
    return predicted.get("mode") == case["mode"] and actual == wanted


def normalize_contract(predicted: dict) -> dict:
    # Production represents plain QA as an execute contract with a read-only
    # answer tool; semantic parsing represents it as answer. Compare their
    # user-visible routing meaning rather than incorrectly calling one an error.
    tasks = predicted.get("tasks") or []
    if tasks and all(task.get("tools") == ["answer_course_question"] for task in tasks):
        return {**predicted, "mode": "answer", "tasks": []}
    return predicted


def macro_f1(rows: list[dict]) -> float:
    # Mode has exactly three defined labels. Unavailable predictions count as errors.
    scores = []
    for label in ("answer", "execute", "clarify"):
        tp = sum(row["expected_mode"] == label and row.get("predicted_mode") == label for row in rows)
        fp = sum(row["expected_mode"] != label and row.get("predicted_mode") == label for row in rows)
        fn = sum(row["expected_mode"] == label and row.get("predicted_mode") != label for row in rows)
        scores.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
    return sum(scores) / len(scores)


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


async def evaluate_intents(provider: BudgetProvider, dataset: dict, split: str, output: Path, done: set) -> None:
    for case in (item for item in dataset["cases"] if item["split"] == split):
        context = ConversationContext(history=(("user", case["previous"]), ("assistant", "练习已完成")) if case["previous"] else (), last_question=case["previous"])
        frame = build_intent_frame(goal=case["goal"], request_message_id=uuid4(),
                                   fallback_topic=follow_up_topic(goal=case["goal"], previous_question=case["previous"])).model_dump(mode="json")
        for variant in ("rules", "production"):
            identity = f"intent:{case['id']}:{variant}"
            if identity in done:
                continue
            provider.case_id = identity
            row = {"id": identity, "category": "intent", "variant": variant, "kind": case["kind"],
                   "goal": case["goal"], "expected_mode": case["mode"], "expected_tasks": case["tasks"], "passed": False}
            started = time.monotonic()
            before = len(provider.responses)
            try:
                prediction = frame
                if variant == "production" and needs_semantic_understanding(case["goal"], frame, context):
                    async with AsyncSessionLocal() as db:
                        prediction = await IntentUnderstandingService(db).resolve(
                            goal=case["goal"], frame=frame, context=context, provider=provider,
                            tools=[{"function": {"name": name}} for name in TOOLS])
                if provider.budget_exhausted:
                    raise BudgetExceeded("Stop after semantic fallback swallowed a budget refusal")
                row.update(predicted_mode=normalize_contract(prediction)["mode"], prediction=prediction,
                           passed=score_contract(case, prediction))
            except BudgetExceeded:
                raise
            except Exception as exc:
                row["error_type"] = type(exc).__name__
            row["seconds"] = round(time.monotonic() - started, 3)
            row["usage"] = [response.usage for response in provider.responses[before:]]
            append(output, row)
            print(identity, "PASS" if row["passed"] else "FAIL", flush=True)
            if provider.consecutive_failures >= 3:
                raise RuntimeError("Three consecutive provider failures; stop spending until connectivity is restored")


async def evaluate_context(provider: BudgetProvider, output: Path, done: set) -> None:
    # Raw history and production packing receive identical original turns.
    # Synthetic facts have random-looking identifiers so general knowledge cannot guess them.
    for index in range(16):
        code = f"LAB-{index * 117 + 593}"
        history = [("user", f"本次学习计划的标记是{code}，后续需要用这个标记。"), ("assistant", "已了解本次计划标记。")]
        for turn in range(30):
            history.extend([("user", f"第{turn + 1}轮：讨论数据结构练习。"),
                            ("assistant", ("课程示例讨论的是元素存储、操作复杂度和边界条件。" * 22))])
        summary = f"学生原话：本次学习计划的标记是{code}，后续需要用这个标记。"
        prompt = "只返回 JSON 对象，字段 plan_code。填写我本次学习计划的标记；无法从上下文知道时填 null。不要猜测。"
        variants = {
            "no_history": [ChatMessage(role="user", content=prompt)],
            "recent_only": ConversationContext(history=tuple(history[-12:])).messages_for(prompt),
            "raw_history": [ChatMessage(role=role, content=text) for role, text in history] + [ChatMessage(role="user", content=prompt)],
            "compacted": ConversationContext(history=tuple(history[-12:]), summary=summary).messages_for(prompt),
        }
        for variant, messages in variants.items():
            identity = f"context:{index:02}:{variant}"
            if identity in done:
                continue
            provider.case_id = identity
            row = {"id": identity, "category": "context", "variant": variant, "passed": False,
                   "expected": code, "synthetic_history_turns": 31,
                   "projection": "controlled source excerpt, not end-to-end worker summarization"}
            started = time.monotonic()
            try:
                response = await provider.chat(messages, temperature=0, max_tokens=96, thinking={"type": "disabled"})
                row.update(content=response.content, usage=response.usage, model=response.model)
                parsed = BaseParser(response.content)
                row["passed"] = parsed.get("plan_code") == code
            except BudgetExceeded:
                raise
            except Exception as exc:
                row["error_type"] = type(exc).__name__
            row["seconds"] = round(time.monotonic() - started, 3)
            append(output, row)
            print(identity, "PASS" if row["passed"] else "FAIL", flush=True)
            if provider.consecutive_failures >= 3:
                raise RuntimeError("Three consecutive provider failures; stop spending until connectivity is restored")


def BaseParser(content: str) -> dict:
    value = content.strip()
    if value.startswith("```"):
        value = "\n".join(line for line in value.splitlines() if not line.startswith("```"))
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Expected an object")
    return parsed


def summarize(output: Path, ledger: EvaluationLedger, split: str) -> dict:
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    groups = {}
    for category in ("intent", "context"):
        for variant in sorted({row["variant"] for row in rows if row["category"] == category}):
            selected = [row for row in rows if row["category"] == category and row["variant"] == variant]
            item = {"total": len(selected), "passed": sum(row["passed"] for row in selected)}
            item["accuracy"] = item["passed"] / item["total"] if item["total"] else None
            if category == "intent":
                item["mode_macro_f1"] = macro_f1(selected)
                item["mode_accuracy"] = sum(row.get("predicted_mode") == row["expected_mode"] for row in selected) / len(selected)
            else:
                item["prompt_tokens"] = sum(row.get("usage", {}).get("prompt_tokens", 0) for row in selected)
                item["completion_tokens"] = sum(row.get("usage", {}).get("completion_tokens", 0) for row in selected)
            groups[f"{category}:{variant}"] = item
    return {"finished_at": datetime.now(UTC).isoformat(), "split": split,
            "configured_model": settings.llm_model_name, "synthetic_evaluation": True,
            "independent_human_review": False, "groups": groups, "budget": ledger.snapshot(),
            "limits": ["mode F1 is three routing modes, not all business intents", "contract exact match is not delivery success",
                       "context projection is controlled, source-preserving; worker quality separately verified", "no semantic teaching-quality score"]}


async def main(args) -> None:
    if settings.llm_provider == "mock" or not settings.llm_api_key or "qwen" not in settings.llm_model_name.lower():
        raise RuntimeError("A configured real Qwen provider is required; evaluation never falls back to Mock")
    dataset = freeze_dataset(BASE / "dataset.json")
    run_name = args.run_name
    if run_name:
        import shutil
        snapshot = BASE / f"{args.split}-{run_name}-source"
        for relative in ("backend/app/services/intent_understanding_service.py", "backend/app/services/conversation_context_service.py",
                         "backend/app/services/context_budget.py", "backend/app/services/prompt_service.py",
                         "backend/app/agent_runtime/intent_contract.py", "backend/app/agent_runtime/supervisor_intents.py",
                         "scripts/evaluate_context_quality.py", "scripts/evaluation_budget.py"):
            destination = snapshot / relative
            source = ROOT / relative
            if destination.exists():
                if destination.read_bytes() != source.read_bytes():
                    raise ValueError("Evaluation code changed after source snapshot; use a new dataset/run version")
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    output = BASE / f"{args.split}-{run_name}-results.jsonl" if run_name else BASE / f"{args.split}-results.jsonl"
    existing = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    done = {row["id"] for row in existing}
    if len(done) != len(existing):
        raise ValueError("Duplicate case results are not allowed")
    ledger = EvaluationLedger(BASE / "budget.sqlite")
    provider = BudgetProvider(OpenAICompatibleLLMProvider(api_key=settings.llm_api_key,
        base_url=settings.llm_base_url, model=settings.llm_model_name, timeout=90), ledger)
    try:
        await evaluate_intents(provider, dataset, args.split, output, done)
        if args.split == "holdout":
            await evaluate_context(provider, output, done)
    finally:
        report = summarize(output, ledger, args.split)
        report["evaluation_status"] = (f"post-fix regression on previously observed synthetic {args.split}" if run_name else "initial frozen synthetic evaluation")
        report_path = BASE / (f"{args.split}-{run_name}-report.json" if run_name else f"{args.split}-report.json")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--run-name", choices=["release"], default="")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(args))
