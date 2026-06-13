#!/usr/bin/env python3
"""stu_01 个性化资源全类型 + 智能对话验收脚本。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

RESOURCE_TYPES: list[tuple[str, str]] = [
    ("explanation", "讲解"),
    ("summary", "总结"),
    ("example", "例题"),
    ("flashcard", "复习卡"),
    ("review", "错题解析"),
    ("mindmap", "思维导图"),
    ("diagram", "图解"),
    ("image", "教学插图"),
    ("video", "讲解视频"),
    ("animation", "动画演示"),
    ("interactive_courseware", "互动课件"),
    ("immersive_classroom", "沉浸课堂"),
    ("code_project", "代码实操"),
    ("reading_pack", "拓展阅读"),
]

DIALOGUE_CASES: list[tuple[str, str]] = [
    ("qa", "栈和队列有什么区别？请结合我的薄弱点简短回答。"),
    ("resource_summary", "请帮我生成一份关于二叉树遍历的总结学习资源。"),
    ("resource_mindmap", "帮我生成二叉树前序遍历的思维导图。"),
]

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "waiting_confirmation"}


class CheckError(RuntimeError):
    pass


@dataclass
class CaseResult:
    name: str
    success: bool
    duration_ms: int
    detail: str = ""
    error: str = ""


@dataclass
class Report:
    resource_results: list[CaseResult] = field(default_factory=list)
    dialogue_results: list[CaseResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CaseResult]:
        return [r for r in self.resource_results + self.dialogue_results if not r.success]


class Stu01Checker:
    def __init__(self, base_url: str, timeout: float, poll_interval: float) -> None:
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout))
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
        params: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        response = self.client.request(
            method,
            path,
            json=json_body,
            params=params,
            headers=self.headers if authenticated else None,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise CheckError(f"{method} {path} 非 JSON 响应 HTTP {response.status_code}") from exc
        if not response.is_success or payload.get("code") != 0:
            raise CheckError(f"{method} {path} 失败: HTTP {response.status_code}, {payload}")
        return payload.get("data")

    def login(self, username: str, password: str) -> None:
        data = self.request(
            "POST",
            "/auth/login",
            json_body={"username": username, "password": password},
            authenticated=False,
        )
        token = data.get("access_token")
        if not token:
            raise CheckError("登录未返回 access_token")
        self.headers = {"Authorization": f"Bearer {token}"}

    def pick_course(self) -> dict[str, Any]:
        page = self.request("GET", "/courses", params={"page": 1, "page_size": 20})
        items = page.get("items") or []
        if not items:
            raise CheckError("stu_01 没有课程，请先运行 seed_stu_01_longterm.py")
        return items[0]

    def pick_knowledge(self, course_id: str) -> str | None:
        try:
            page = self.request(
                "GET",
                "/knowledge/points",
                params={"course_id": course_id, "page": 1, "page_size": 5},
            )
            items = page.get("items") or []
            return items[0]["id"] if items else None
        except CheckError:
            return None

    def generate_resource(
        self,
        *,
        course_id: str,
        resource_type: str,
        label: str,
        knowledge_id: str | None,
    ) -> CaseResult:
        started = time.perf_counter()
        body: dict[str, Any] = {
            "course_id": course_id,
            "resource_type": resource_type,
            "requirement": f"服务器验收：请用适合初学者的方式生成{label}，保留来源提示，内容尽量简短。",
            "use_profile": True,
        }
        if knowledge_id:
            body["knowledge_id"] = knowledge_id
        try:
            data = self.request("POST", "/resources/generate", json_body=body)
            resource = data.get("resource") or data
            title = resource.get("title") or ""
            content_len = len(str(resource.get("content") or ""))
            preview = resource.get("preview_mode") or "text"
            if content_len < 50:
                raise CheckError(f"内容过短 ({content_len} 字符)")
            duration_ms = round((time.perf_counter() - started) * 1000)
            return CaseResult(
                name=f"resource/{resource_type}",
                success=True,
                duration_ms=duration_ms,
                detail=f"title={title[:40]}, len={content_len}, preview={preview}",
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            return CaseResult(
                name=f"resource/{resource_type}",
                success=False,
                duration_ms=duration_ms,
                error=str(exc),
            )

    def wait_task(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        last_status = "unknown"
        while time.monotonic() < deadline:
            task = self.request("GET", f"/agent/tasks/{task_id}")
            last_status = str(task.get("status") or "unknown")
            if last_status in TERMINAL_STATUSES:
                return task
            time.sleep(self.poll_interval)
        raise CheckError(f"任务超时 task_id={task_id}, last_status={last_status}")

    def run_dialogue(
        self,
        *,
        course_id: str,
        case_id: str,
        content: str,
    ) -> CaseResult:
        started = time.perf_counter()
        try:
            conv = self.request(
                "POST",
                "/agent/conversations",
                json_body={"course_id": course_id, "title": f"stu_01 验收-{case_id}"},
            )
            conversation_id = conv["id"]
            accepted = self.request(
                "POST",
                f"/agent/conversations/{conversation_id}/messages",
                json_body={"content": content},
            )
            task_id = accepted["task"]["id"]
            task = self.wait_task(task_id)
            messages = self.request("GET", f"/agent/conversations/{conversation_id}/messages").get("items") or []
            assistant_msgs = [m for m in messages if m.get("role") == "assistant" and m.get("content")]
            status = task.get("status")
            if status != "succeeded":
                raise CheckError(f"Agent 任务失败: status={status}, error={task.get('error_message')}")
            if not assistant_msgs:
                raise CheckError("对话未产生 assistant 回复")
            excerpt = str(assistant_msgs[-1].get("content") or "")[:120]
            duration_ms = round((time.perf_counter() - started) * 1000)
            return CaseResult(
                name=f"dialogue/{case_id}",
                success=True,
                duration_ms=duration_ms,
                detail=f"status={status}, reply={excerpt}",
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            return CaseResult(
                name=f"dialogue/{case_id}",
                success=False,
                duration_ms=duration_ms,
                error=str(exc),
            )


def run(args: argparse.Namespace) -> Report:
    checker = Stu01Checker(args.base_url, args.timeout, args.poll_interval)
    report = Report()
    try:
        checker.login(args.username, args.password)
        course = checker.pick_course()
        course_id = course["id"]
        knowledge_id = checker.pick_knowledge(course_id)
        print(f"[INFO] 使用课程: {course.get('title')} ({course_id})", flush=True)
        if knowledge_id:
            print(f"[INFO] 使用知识点: {knowledge_id}", flush=True)

        for resource_type, label in RESOURCE_TYPES:
            if args.skip_types and resource_type in args.skip_types:
                print(f"[SKIP] resource/{resource_type}", flush=True)
                continue
            result = checker.generate_resource(
                course_id=course_id,
                resource_type=resource_type,
                label=label,
                knowledge_id=knowledge_id,
            )
            report.resource_results.append(result)
            mark = "PASS" if result.success else "FAIL"
            print(
                f"[{mark}] {result.name:<32} {result.duration_ms:>7} ms  "
                f"{result.detail or result.error}",
                flush=True,
            )

        for case_id, content in DIALOGUE_CASES:
            result = checker.run_dialogue(course_id=course_id, case_id=case_id, content=content)
            report.dialogue_results.append(result)
            mark = "PASS" if result.success else "FAIL"
            print(
                f"[{mark}] {result.name:<32} {result.duration_ms:>7} ms  "
                f"{result.detail or result.error}",
                flush=True,
            )
        return report
    finally:
        checker.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="stu_01 个性化资源 + 智能对话验收")
    parser.add_argument("--base-url", default="http://127.0.0.1/api/v1")
    parser.add_argument("--username", default="stu_01")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--json-output", default="/tmp/stu01_resource_dialogue_report.json")
    parser.add_argument(
        "--skip-types",
        nargs="*",
        default=[],
        help="跳过的资源类型，例如 immersive_classroom",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    report = run(args)
    total_ms = round((time.perf_counter() - started) * 1000)
    passed = sum(1 for r in report.resource_results + report.dialogue_results if r.success)
    total = len(report.resource_results) + len(report.dialogue_results)
    summary = {
        "username": args.username,
        "base_url": args.base_url,
        "passed": passed,
        "total": total,
        "failed": [{"name": r.name, "error": r.error} for r in report.failed],
        "resource_results": [r.__dict__ for r in report.resource_results],
        "dialogue_results": [r.__dict__ for r in report.dialogue_results],
        "total_duration_ms": total_ms,
    }
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n验收完成: {passed}/{total} 通过, 耗时 {total_ms} ms", flush=True)
    print(f"报告: {args.json_output}", flush=True)
    if report.failed:
        print("失败项:", file=sys.stderr)
        for item in report.failed:
            print(f"  - {item.name}: {item.error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
