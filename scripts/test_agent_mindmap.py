#!/usr/bin/env python3
"""验证 Agent 对话路径 generate_mindmap 是否成功。"""

from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
COURSE_ID = "393d39d6-d18a-4389-9e67-267c42bd8be5"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(300.0))
    login = client.post("/auth/login", json={"username": "stu_01", "password": "123456"}).json()
    if login.get("code") != 0:
        print("login failed", file=sys.stderr)
        return 1
    headers = {"Authorization": f"Bearer {login['data']['access_token']}"}

    conv = client.post("/agent/conversations", headers=headers, json={"course_id": COURSE_ID}).json()
    conv_id = conv["data"]["id"]
    msg = client.post(
        f"/agent/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "给我生成队列知识点的思维导图"},
    ).json()
    if msg.get("code") != 0:
        print("send failed:", msg, file=sys.stderr)
        return 1
    task_id = msg["data"]["task"]["id"]
    print("task_id=", task_id)

    for _ in range(90):
        time.sleep(2)
        task = client.get(f"/agent/tasks/{task_id}", headers=headers).json()["data"]
        status = task.get("status")
        events = client.get(f"/agent/tasks/{task_id}/events/history", headers=headers).json()["data"]["items"]
        def payload(e: dict) -> dict:
            return e.get("payload") or e.get("data") or {}

        failed = [
            e for e in events
            if e.get("event_type") == "tool_completed"
            and payload(e).get("tool_name") == "generate_mindmap"
            and payload(e).get("success") is False
        ]
        if failed:
            err = payload(failed[0]).get("error_message") or payload(failed[0]).get("message")
            print("FAIL generate_mindmap:", err, file=sys.stderr)
            return 1
        success = [
            e for e in events
            if e.get("event_type") == "tool_completed"
            and payload(e).get("tool_name") == "generate_mindmap"
            and payload(e).get("success") is True
        ]
        if success:
            print("OK generate_mindmap succeeded, task_status=", status)
            return 0
        if status in {"failed", "cancelled"}:
            print("task failed:", status, task.get("error_message"), file=sys.stderr)
            return 1
        print("waiting...", status, "events", len(events))

    print("timeout", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
