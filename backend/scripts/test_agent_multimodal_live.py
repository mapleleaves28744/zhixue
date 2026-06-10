"""Live API: Agent routes BFS illustration + queue speech synthesis."""

from __future__ import annotations

import sys
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
TERMINAL = {"succeeded", "failed", "cancelled", "waiting_confirmation"}


def api(client: httpx.Client, method: str, path: str, **kwargs) -> dict:
    response = client.request(method, BASE + path, **kwargs)
    body = response.json()
    if response.status_code >= 400 or body.get("code") != 0:
        raise RuntimeError(f"{method} {path} failed: HTTP {response.status_code} {body}")
    return body["data"]


def wait_task(client: httpx.Client, headers: dict, task_id: str, timeout: float = 180.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = api(client, "GET", f"/agent/tasks/{task_id}", headers=headers)
        if task.get("status") in TERMINAL:
            return task
        time.sleep(2.0)
    raise RuntimeError(f"task {task_id} timed out")


def tool_names(task: dict) -> list[str]:
    names: list[str] = []
    plan = task.get("plan_json") or {}
    for item in plan.get("tool_calls") or []:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return list(dict.fromkeys(names))


def run_scenario(
    client: httpx.Client,
    headers: dict,
    conversation_id: str,
    content: str,
    expected_any: set[str],
    label: str,
) -> dict:
    print(f"\n--- {label} ---")
    accepted = api(
        client,
        "POST",
        f"/agent/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": content},
    )
    task_id = accepted["task"]["id"]
    print(f"task_id: {task_id}")
    task = wait_task(client, headers, task_id)
    status = task.get("status")
    tools = tool_names(task)
    print(f"status: {status}")
    print(f"tools: {tools}")
    if status != "succeeded":
        raise RuntimeError(f"{label} failed: {task.get('error_message')}")
    if not expected_any.intersection(tools):
        raise RuntimeError(f"{label}: expected one of {expected_any}, got {tools}")
    messages = api(client, "GET", f"/agent/conversations/{conversation_id}/messages", headers=headers)
    assistant = [m for m in messages.get("items", []) if m.get("role") == "assistant" and m.get("content")]
    if not assistant:
        raise RuntimeError(f"{label}: no assistant message persisted")
    excerpt = str(assistant[-1]["content"])[:160].replace("\n", " ")
    print(f"answer excerpt: {excerpt}")
    return task


def main() -> int:
    uname = f"mm_live_{uuid.uuid4().hex[:8]}"
    password = "Test123456!"

    with httpx.Client(timeout=120.0) as client:
        print("[setup] register + login")
        api(
            client,
            "POST",
            "/auth/register",
            json={
                "username": uname,
                "email": f"{uname}@test.local",
                "password": password,
                "display_name": "mm-live",
            },
        )
        login = api(client, "POST", "/auth/login", json={"username": uname, "password": password})
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        course_id = api(
            client,
            "POST",
            "/courses",
            headers=headers,
            json={"title": "多模态 Agent 联调", "description": "live"},
        )["id"]
        conv_id = api(
            client,
            "POST",
            "/agent/conversations",
            headers=headers,
            json={"course_id": course_id, "title": "multimodal live"},
        )["id"]

        run_scenario(
            client,
            headers,
            conv_id,
            "请帮我生成一张 BFS 广度优先搜索的教学插图，清晰标注队列进出过程",
            {"generate_educational_image", "generate_diagram", "generate_mindmap"},
            "BFS illustration",
        )

        run_scenario(
            client,
            headers,
            conv_id,
            "生成讲解队列的语音，简短概括 FIFO 与 BFS 的关系",
            {"synthesize_speech", "generate_explanation"},
            "queue speech",
        )

    print("\nPASS: Agent multimodal live scenarios verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
