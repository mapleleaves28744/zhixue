"""120 reproducible contract fixtures plus optional real semantic parser probes.

Template families are development regressions, not a held-out or blind accuracy set.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.agent_runtime.intent_contract import build_intent_frame, follow_up_topic
from app.services.conversation_context_service import ConversationContext

TOPICS = ["栈", "队列", "链表", "数组", "二叉树", "二叉搜索树", "AVL树", "红黑树", "哈希表", "堆",
          "冒泡排序", "插入排序", "选择排序", "归并排序", "快速排序", "堆排序", "递归", "回溯", "拓扑排序", "并查集"]


def evaluate_rules():
    results = []
    for index, topic in enumerate(TOPICS):
        other = TOPICS[(index+1) % len(TOPICS)]
        for kind in ("single", "combination", "exclude", "followup", "clarify", "revision_source"):
            result = {"id": f"{kind}_{index+1}", "passed": False}
            try:
                source, origin = uuid4(), uuid4()
                goal = f"给{topic}出练习题"
                kwargs = {}
                if kind == "combination": goal += f"，给{other}出练习题"
                if kind == "exclude": kwargs["skip_tools"] = ["generate_quiz"]
                if kind in {"followup", "clarify"}: goal = "再给我五道同类题"
                if kind == "followup": kwargs["fallback_topic"] = follow_up_topic(goal=goal, previous_question=f"给{topic}出练习题")
                if kind == "revision_source": kwargs.update(revision=2, original_request_message_id=origin)
                frame = build_intent_frame(goal=goal, request_message_id=source, **kwargs)
                if kind == "clarify": assert frame.mode == "clarify" and not frame.tasks
                elif kind == "exclude": assert not frame.tasks and frame.exclusions == ["generate_quiz"]
                else:
                    assert [item.topic for item in frame.tasks] == ([topic, other] if kind == "combination" else [topic])
                    assert all(item.tools == ["generate_quiz"] for item in frame.tasks)
                    assert all(item.source_message_id == (origin if kind == "revision_source" else source) for item in frame.tasks)
                result["passed"] = True
            except Exception as exc: result["error"] = f"{type(exc).__name__}: {exc}"
            results.append(result)
    return results


async def semantic_probes(owner: UUID, course: UUID):
    from app.db.session import AsyncSessionLocal
    from app.llm.provider import get_llm_provider
    from app.services.intent_understanding_service import IntentUnderstandingService
    tools = [{"function": {"name": name}} for name in ("generate_quiz", "generate_explanation", "generate_mindmap", "generate_diagram")]
    probes = [
        ("栈和队列各出练习题", ["栈", "队列"], []),
        ("二叉树和哈希表分别生成讲解资源", ["二叉树", "哈希表"], []),
        ("给栈出练习题，给链表出练习题", ["栈", "链表"], []),
        ("给归并排序出练习题，给快速排序出练习题", ["归并排序", "快速排序"], []),
        ("栈和队列各生成讲解，不要练习题", ["栈", "队列"], ["generate_quiz"]),
        ("给二叉树出练习题\n学生最新修订（优先于之前要求）：改成队列的练习题", ["队列"], []),
    ]
    results = []
    for goal, expected, excluded in probes:
        result = {"goal": goal, "passed": False}
        try:
            async with AsyncSessionLocal() as db:
                source = uuid4()
                frame = build_intent_frame(goal=goal, request_message_id=source, skip_tools=excluded).model_dump(mode="json")
                resolved = await IntentUnderstandingService(db).resolve(goal=goal, frame=frame, context=ConversationContext(),
                    provider=get_llm_provider(db=db, user_id=owner, course_id=course, allow_mock_fallback=False), tools=tools)
                result["resolved"] = resolved
                assert resolved["parser"] == "semantic_v1", "Model understanding was unavailable"
                assert sorted(item["topic"] for item in resolved["tasks"]) == sorted(expected)
                assert all(item["source_message_id"] == str(source) for item in resolved["tasks"])
                assert not any(name in excluded for item in resolved["tasks"] for name in item["tools"])
                result["passed"] = True
        except Exception as exc: result["error"] = f"{type(exc).__name__}: {exc}"
        results.append(result)
        print("semantic", "PASS" if result["passed"] else result["error"], flush=True)
    return results


async def main(args):
    from app.core.config import settings
    rules = evaluate_rules()
    semantic = await semantic_probes(args.user_id, args.course_id) if args.user_id and args.course_id else []
    report = {"finished_at": datetime.now(UTC).isoformat(), "configured_model": settings.llm_model_name, "type": "development fixtures; no held-out/semantic quality accuracy claim",
        "rule_passed": sum(item["passed"] for item in rules), "rule_total": len(rules), "rules": rules,
        "semantic_passed": sum(item["passed"] for item in semantic), "semantic_total": len(semantic), "semantic": semantic}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Contracts {report['rule_passed']}/{len(rules)}; real semantic {report['semantic_passed']}/{len(semantic)}")
    return all(item["passed"] for item in [*rules, *semantic])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=UUID)
    parser.add_argument("--course-id", type=UUID)
    parser.add_argument("--output", type=Path, default=ROOT / "data/seed_knowledge/data_structure/eval/baselines/intent_contract_acceptance.json")
    args = parser.parse_args()
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(0 if asyncio.run(main(args)) else 1)
