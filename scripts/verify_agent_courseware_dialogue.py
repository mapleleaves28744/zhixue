#!/usr/bin/env python3
"""Agent 智能对话模式：PPT/课件 意图 → generate_interactive_courseware 端到端验收。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx

TERMINAL = {"succeeded", "failed", "cancelled", "waiting_confirmation"}


def api(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    resp = client.request(method, path, **kwargs)
    if not resp.content:
        raise RuntimeError(f"{method} {path} -> empty response (status={resp.status_code})")
    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {path} -> non-json (status={resp.status_code}): {resp.text[:200]}") from exc
    if payload.get("code") != 0:
        raise RuntimeError(f"{method} {path} -> {payload}")
    return payload["data"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1/api/v1")
    parser.add_argument("--username", default="stu_01")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--goal", default="生成图和二叉树的讲解ppt")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=httpx.Timeout(120.0))
    token = api(client, "POST", "/auth/login", json={"username": args.username, "password": args.password})[
        "access_token"
    ]
    client.headers["Authorization"] = f"Bearer {token}"

    courses = api(client, "GET", "/courses", params={"page": 1, "page_size": 5})
    course_id = courses["items"][0]["id"]
    conv = api(client, "POST", "/agent/conversations", json={"course_id": course_id, "title": "课件验收对话"})
    accepted = api(
        client,
        "POST",
        f"/agent/conversations/{conv['id']}/messages",
        json={"content": args.goal},
    )
    task_id = accepted["task"]["id"]
    print(f"[INFO] task_id={task_id} goal={args.goal!r}")

    deadline = time.monotonic() + args.timeout
    tool_names: list[str] = []
    final_status = "running"
    error_message = ""
    while time.monotonic() < deadline:
        task = api(client, "GET", f"/agent/tasks/{task_id}")
        final_status = str(task.get("status") or "running")
        error_message = str(task.get("error_message") or "")
        events = api(client, "GET", f"/agent/tasks/{task_id}/events/history")
        items = events.get("items") or []
        for evt in items:
            payload = evt.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            for call in payload.get("tool_calls") or []:
                name = str(call.get("name") or "")
                if name and name not in tool_names:
                    tool_names.append(name)
            if evt.get("event_type") == "tool_completed":
                name = str(payload.get("tool_name") or "")
                if name and name not in tool_names:
                    tool_names.append(name)
        if final_status in TERMINAL:
            break
        time.sleep(2)

    messages = api(client, "GET", f"/agent/conversations/{conv['id']}/messages")
    message_items = messages.get("items") if isinstance(messages, dict) else messages
    assistant = [m for m in message_items if m.get("role") == "assistant" and m.get("content")]
    reply = str(assistant[-1]["content"]) if assistant else ""

    result = {
        "passed": False,
        "task_status": final_status,
        "tool_names": tool_names,
        "error_message": error_message,
        "reply_preview": reply[:240],
        "checks": {},
    }

    result["checks"]["task_terminal"] = final_status in TERMINAL
    result["checks"]["used_courseware_tool"] = "generate_interactive_courseware" in tool_names
    result["checks"]["not_video_tool"] = "generate_lesson_video" not in tool_names
    result["checks"]["task_not_failed"] = final_status != "failed"
    result["checks"]["reply_not_fake_video_success"] = "视频任务已创建成功" not in reply

    result["passed"] = all(result["checks"].values())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
