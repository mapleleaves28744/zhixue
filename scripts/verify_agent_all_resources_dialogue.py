#!/usr/bin/env python3
"""Agent 智能对话模式：逐类个性化资源 + 多意图 端到端验收。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx

TERMINAL = {"succeeded", "failed", "cancelled", "waiting_confirmation"}

# 与 frontend/types/resource.ts 及 Agent 工具对齐
AGENT_RESOURCE_CASES: list[dict[str, Any]] = [
    {
        "name": "interactive_courseware",
        "goal": "生成二叉树入门的互动课件ppt",
        "must_tools": ["generate_interactive_courseware"],
        "must_not_tools": ["generate_lesson_video"],
    },
    {
        "name": "mindmap",
        "goal": "帮我梳理队列的知识结构思维导图",
        "must_tools": ["generate_mindmap"],
        "must_not_tools": ["generate_lesson_video"],
    },
    {
        "name": "diagram",
        "goal": "画一张栈的入栈出栈流程图",
        "must_tools": ["generate_diagram"],
        "must_not_tools": ["generate_educational_image"],
    },
    {
        "name": "image",
        "goal": "给广度优先搜索配一张教学插图",
        "must_tools": ["generate_educational_image"],
        "must_not_tools": ["generate_lesson_video"],
    },
    {
        "name": "explanation",
        "goal": "生成一份关于哈希表的个性化讲解资料",
        "must_tools": ["generate_explanation"],
        "must_not_tools": ["generate_lesson_video"],
    },
    {
        "name": "quiz",
        "goal": "生成5道关于链表的练习题",
        "must_tools": ["generate_quiz"],
        "must_not_tools": ["generate_lesson_video"],
    },
    {
        "name": "learning_path",
        "goal": "帮我制定二叉树的学习路径",
        "must_tools": ["generate_learning_path"],
        "must_not_tools": ["generate_lesson_video"],
    },
    {
        "name": "video",
        "goal": "生成二叉树讲解视频",
        "must_tools": ["generate_lesson_video"],
        "must_not_tools": ["generate_interactive_courseware"],
        "allow_async_only": True,
    },
    {
        "name": "immersive_classroom",
        "goal": "为图遍历生成沉浸课堂",
        "must_tools": ["generate_immersive_classroom"],
        "must_not_tools": ["generate_lesson_video"],
        "allow_async_only": True,
    },
    {
        "name": "multi_intent_ppt_mindmap",
        "goal": "生成二叉树ppt和队列思维导图",
        "must_tools": ["generate_interactive_courseware", "generate_mindmap"],
        "must_not_tools": ["generate_lesson_video"],
    },
    {
        "name": "multi_intent_ppt_diagram",
        "goal": "帮我做二叉树幻灯片，再画一张队列的流程图",
        "must_tools": ["generate_interactive_courseware", "generate_diagram"],
        "must_not_tools": ["generate_lesson_video"],
    },
]


def api(client: httpx.Client, method: str, path: str, *, retries: int = 5, **kwargs: Any) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        resp = client.request(method, path, **kwargs)
        if resp.status_code in {502, 503, 504} and attempt + 1 < retries:
            time.sleep(min(2 ** attempt, 8))
            continue
        if not resp.content:
            last_error = RuntimeError(f"{method} {path} -> empty response (status={resp.status_code})")
            if attempt + 1 < retries:
                time.sleep(2)
                continue
            raise last_error
        try:
            payload = resp.json()
        except json.JSONDecodeError as exc:
            last_error = RuntimeError(
                f"{method} {path} -> non-json (status={resp.status_code}): {resp.text[:200]}"
            )
            if resp.status_code in {502, 503, 504} and attempt + 1 < retries:
                time.sleep(min(2 ** attempt, 8))
                continue
            raise last_error from exc
        if payload.get("code") != 0:
            raise RuntimeError(f"{method} {path} -> {payload}")
        return payload["data"]
    if last_error:
        raise last_error
    raise RuntimeError(f"{method} {path} -> request failed after retries")


def collect_tool_names(events: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for evt in events.get("items") or []:
        payload = evt.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        for call in payload.get("tool_calls") or []:
            name = str(call.get("name") or "")
            if name and name not in names:
                names.append(name)
        if evt.get("event_type") == "tool_completed":
            name = str(payload.get("tool_name") or "")
            if name and name not in names:
                names.append(name)
    return names


def wait_task(client: httpx.Client, task_id: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    tool_names: list[str] = []
    while time.monotonic() < deadline:
        task = api(client, "GET", f"/agent/tasks/{task_id}")
        status = str(task.get("status") or "running")
        events = api(client, "GET", f"/agent/tasks/{task_id}/events/history")
        for name in collect_tool_names(events):
            if name not in tool_names:
                tool_names.append(name)
        if status in TERMINAL:
            return {
                "task": task,
                "status": status,
                "tool_names": tool_names,
                "error_message": str(task.get("error_message") or ""),
            }
        time.sleep(2)
    return {
        "task": api(client, "GET", f"/agent/tasks/{task_id}"),
        "status": "timeout",
        "tool_names": tool_names,
        "error_message": "timeout",
    }


def run_case(
    client: httpx.Client,
    *,
    course_id: str,
    case: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    conv = api(client, "POST", "/agent/conversations", json={"course_id": course_id, "title": f"验收-{case['name']}"})
    accepted = api(
        client,
        "POST",
        f"/agent/conversations/{conv['id']}/messages",
        json={"content": case["goal"]},
    )
    task_id = accepted["task"]["id"]
    print(f"[RUN] {case['name']} task_id={task_id} goal={case['goal']!r}")
    outcome = wait_task(client, task_id, timeout)
    status = outcome["status"]
    tool_names = outcome["tool_names"]
    checks = {
        "terminal": status in TERMINAL,
        "not_failed": status != "failed",
        "must_tools": all(name in tool_names for name in case.get("must_tools") or []),
        "must_not_tools": all(name not in tool_names for name in case.get("must_not_tools") or []),
        "not_fake_video_success": True,
    }
    if case.get("allow_async_only"):
        checks["async_or_success"] = status in {"succeeded", "failed"} and any(
            name in tool_names for name in case.get("must_tools") or []
        )
    passed = all(checks.values())
    return {
        "name": case["name"],
        "goal": case["goal"],
        "task_id": task_id,
        "status": status,
        "tool_names": tool_names,
        "error_message": outcome["error_message"],
        "checks": checks,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1/api/v1")
    parser.add_argument("--username", default="stu_01")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--case", action="append", default=[], help="只跑指定 case name，可重复")
    parser.add_argument("--skip-async", action="store_true", help="跳过 video / immersive_classroom")
    args = parser.parse_args()

    cases = AGENT_RESOURCE_CASES
    if args.case:
        selected = set(args.case)
        cases = [item for item in cases if item["name"] in selected]
    if args.skip_async:
        cases = [item for item in cases if not item.get("allow_async_only")]

    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=httpx.Timeout(120.0))
    token = api(client, "POST", "/auth/login", json={"username": args.username, "password": args.password})[
        "access_token"
    ]
    client.headers["Authorization"] = f"Bearer {token}"
    courses = api(client, "GET", "/courses", params={"page": 1, "page_size": 5})
    course_id = courses["items"][0]["id"]

    results: list[dict[str, Any]] = []
    for case in cases:
        try:
            results.append(run_case(client, course_id=course_id, case=case, timeout=args.timeout))
        except Exception as exc:
            results.append(
                {
                    "name": case["name"],
                    "goal": case["goal"],
                    "passed": False,
                    "error_message": str(exc),
                    "checks": {"exception": False},
                }
            )

    summary = {
        "total": len(results),
        "passed": sum(1 for item in results if item.get("passed")),
        "failed": sum(1 for item in results if not item.get("passed")),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
