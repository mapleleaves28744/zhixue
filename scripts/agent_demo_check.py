from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx


PROFILE_MESSAGE = (
    "我是软件工程大二学生，学习目标是期末数据结构拿到 85 分以上。"
    "我递归和二叉树遍历比较薄弱，经常漏掉边界条件。"
    "我喜欢 Python 代码示例、分步骤讲解和短一点的总结，请记住我的学习偏好。"
)
PLAN_MESSAGE = "请根据刚才记录的画像，为我安排一个三天的数据结构补弱学习计划。"
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "waiting_confirmation"}


class AgentDemoFailed(RuntimeError):
    pass


@dataclass
class DemoTaskResult:
    task: dict[str, Any]
    events: list[dict[str, Any]]
    messages: list[dict[str, Any]]

    @property
    def event_types(self) -> list[str]:
        return [item["event_type"] for item in self.events]

    @property
    def tool_names(self) -> list[str]:
        names: list[str] = []
        plan = self.task.get("plan_json") or {}
        for item in plan.get("tool_calls") or []:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        for event in self.events:
            if event["event_type"] == "tool_started" and event["payload"].get("tool_name"):
                names.append(str(event["payload"]["tool_name"]))
        return list(dict.fromkeys(names))


class AgentDemoCheck:
    def __init__(self, base_url: str, timeout: float, poll_interval: float) -> None:
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
        )
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.headers: dict[str, str] = {}

    def close(self) -> None:
        self.client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        response = self.client.request(
            method,
            path,
            json=json_body,
            headers=self.headers if authenticated else None,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AgentDemoFailed(f"{method} {path} returned non-JSON HTTP {response.status_code}") from exc
        if not response.is_success or payload.get("code") != 0:
            raise AgentDemoFailed(f"{method} {path} failed: HTTP {response.status_code}, {payload}")
        return payload.get("data")

    def register_and_login(self, username: str, password: str) -> dict[str, Any]:
        self.assert_current_backend()
        try:
            self.request(
                "POST",
                "/auth/register",
                json_body={
                    "username": username,
                    "email": f"{username}@example.test",
                    "password": password,
                    "role": "student",
                },
                authenticated=False,
            )
        except AgentDemoFailed:
            # The demo script is repeatable for an existing demo account if the same
            # password is used; login below is the authoritative check.
            pass
        login = self.request(
            "POST",
            "/auth/login",
            json_body={"username": username, "password": password},
            authenticated=False,
        )
        token = login.get("access_token")
        if not token:
            raise AgentDemoFailed("login did not return access_token")
        self.headers = {"Authorization": f"Bearer {token}"}
        return login

    def assert_current_backend(self) -> None:
        api_base = str(self.client.base_url).rstrip("/")
        root_base = api_base[: -len("/api/v1")] if api_base.endswith("/api/v1") else api_base
        response = self.client.get(f"{root_base}/openapi.json")
        if not response.is_success:
            raise AgentDemoFailed(f"openapi check failed: HTTP {response.status_code}")
        try:
            paths = set((response.json().get("paths") or {}).keys())
        except ValueError as exc:
            raise AgentDemoFailed("openapi check returned non-JSON response") from exc
        required = {
            "/api/v1/agent/conversations",
            "/api/v1/agent/conversations/{conversation_id}/messages",
            "/api/v1/student/profile/dialogue-ingest",
        }
        missing = sorted(required - paths)
        if missing:
            raise AgentDemoFailed(
                "当前后端不是最新 Phase 3.1/Phase 4 代码，缺少接口: "
                + ", ".join(missing)
            )

    def create_course(self, suffix: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/courses",
            json_body={
                "title": f"Phase 3.1 Agent 演示课 {suffix}",
                "course_code": f"AGENT-{suffix[-8:]}",
                "description": "用于验证 LangGraph Agent 与对话式画像的稳定演示课程。",
                "subject": "数据结构",
                "visibility": "private",
            },
        )

    def create_conversation(self, course_id: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/agent/conversations",
            json_body={"course_id": course_id, "title": "Phase 3.1 稳定演示"},
        )

    def send_and_wait(
        self,
        conversation_id: str,
        content: str,
        *,
        expected_tool: str,
    ) -> DemoTaskResult:
        accepted = self.request(
            "POST",
            f"/agent/conversations/{conversation_id}/messages",
            json_body={"content": content},
        )
        task_id = accepted["task"]["id"]
        task = self.wait_task(task_id)
        events = self.read_events(task_id)
        messages = self.request("GET", f"/agent/conversations/{conversation_id}/messages")["items"]
        result = DemoTaskResult(task=task, events=events, messages=messages)
        self.assert_task(result, expected_tool=expected_tool)
        return result

    def wait_task(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        last_status = "unknown"
        while time.monotonic() < deadline:
            task = self.request("GET", f"/agent/tasks/{task_id}")
            last_status = str(task.get("status") or "unknown")
            if last_status in TERMINAL_STATUSES:
                return task
            time.sleep(self.poll_interval)
        raise AgentDemoFailed(
            f"task {task_id} timed out, last_status={last_status}. "
            "If status stayed queued, start arq worker via scripts/start_dev.ps1 "
            "or run backend/scripts/recover_orphaned_agent_tasks.py."
        )

    def read_events(self, task_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        current_type: str | None = None
        current_data: dict[str, Any] | None = None
        with self.client.stream(
            "GET",
            f"/agent/tasks/{task_id}/events",
            headers={**self.headers, "Accept": "text/event-stream"},
        ) as response:
            if not response.is_success:
                raise AgentDemoFailed(f"event stream failed: HTTP {response.status_code}")
            for raw_line in response.iter_lines():
                line = raw_line.strip()
                if not line:
                    if current_type:
                        events.append({"event_type": current_type, "payload": current_data or {}})
                    current_type = None
                    current_data = None
                    continue
                if line.startswith("event:"):
                    current_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    try:
                        current_data = json.loads(line.split(":", 1)[1].strip())
                    except json.JSONDecodeError:
                        current_data = {}
        return events

    def assert_task(self, result: DemoTaskResult, *, expected_tool: str) -> None:
        status = result.task.get("status")
        if status != "succeeded":
            raise AgentDemoFailed(f"Agent task did not succeed: {status}, {result.task.get('error_message')}")
        if expected_tool not in result.tool_names:
            raise AgentDemoFailed(
                f"Expected tool {expected_tool!r}, got tools={result.tool_names}, events={result.event_types}"
            )
        if "tool_started" not in result.event_types or "completed" not in result.event_types:
            raise AgentDemoFailed(f"Agent events are incomplete: {result.event_types}")
        if not any(item.get("role") == "assistant" and item.get("content") for item in result.messages):
            raise AgentDemoFailed("Conversation did not persist assistant final message")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3.1 LangGraph Agent stable demo smoke check.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1", help="API v1 base URL")
    parser.add_argument("--timeout", type=float, default=300.0, help="seconds to wait for each Agent task")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="task polling interval seconds")
    parser.add_argument("--username", help="optional reusable demo username")
    parser.add_argument("--password", default="AgentDemo2026!", help="demo account password")
    parser.add_argument("--json-output", help="write summary JSON to this path")
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    demo = AgentDemoCheck(args.base_url, args.timeout, args.poll_interval)
    suffix = str(int(time.time() * 1000))
    username = args.username or f"agent_demo_{suffix}"
    try:
        login = demo.register_and_login(username, args.password)
        course = demo.create_course(suffix)
        conversation = demo.create_conversation(course["id"])
        profile_result = demo.send_and_wait(
            conversation["id"],
            PROFILE_MESSAGE,
            expected_tool="update_profile_from_dialogue",
        )
        unexpected_profile_tools = [
            name for name in profile_result.tool_names if name != "update_profile_from_dialogue"
        ]
        if unexpected_profile_tools:
            raise AgentDemoFailed(
                "Profile-only request expanded into unrelated tools: "
                + ", ".join(unexpected_profile_tools)
            )
        plan_result = demo.send_and_wait(
            conversation["id"],
            PLAN_MESSAGE,
            expected_tool="generate_learning_path",
        )
        profile = demo.request("GET", "/student/profile")
        dialogue_profile = (profile.get("strategy_summary") or {}).get("dialogue_profile") or {}
        if not dialogue_profile.get("dimensions"):
            raise AgentDemoFailed("Profile dialogue evidence was not persisted")
        return {
            "username": username,
            "user_id": login["user"]["id"],
            "course_id": course["id"],
            "conversation_id": conversation["id"],
            "profile_task": summarize_task(profile_result),
            "plan_task": summarize_task(plan_result),
            "dialogue_profile": dialogue_profile,
            "assistant_url": "http://127.0.0.1:3000/assistant",
            "api_base_url": args.base_url,
        }
    finally:
        demo.close()


def summarize_task(result: DemoTaskResult) -> dict[str, Any]:
    messages = [item for item in result.messages if item.get("role") == "assistant"]
    return {
        "task_id": result.task["id"],
        "status": result.task["status"],
        "tools": result.tool_names,
        "event_types": result.event_types,
        "iteration_count": result.task.get("iteration_count"),
        "tool_call_count": result.task.get("tool_call_count"),
        "answer_excerpt": str(messages[-1].get("content") if messages else "")[:240],
    }


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    try:
        summary = run(args)
    except (AgentDemoFailed, httpx.HTTPError) as exc:
        print(f"\n[FAIL] Phase 3.1 Agent demo check failed: {exc}", file=sys.stderr)
        return 1
    summary["total_duration_ms"] = round((time.perf_counter() - started) * 1000)
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as output:
            json.dump(summary, output, ensure_ascii=False, indent=2)
    print("\nPhase 3.1 Agent stable demo check passed")
    # Keep console output ASCII-safe on Windows PowerShell, whose default
    # encoding may be GBK. The optional JSON artifact still preserves Unicode.
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
