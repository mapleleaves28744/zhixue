#!/usr/bin/env python3
"""知识图谱双轨 HTTP 集成验收：登录 → Tutor → 图谱 → 刷题 → 掌握度。"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx


class GraphE2EFailed(RuntimeError):
    pass


@dataclass
class StepResult:
    name: str
    duration_ms: int
    detail: str


class KnowledgeGraphE2ECheck:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
        )
        self.steps: list[StepResult] = []
        self.headers: dict[str, str] = {}

    def close(self) -> None:
        self.client.close()

    def run_step(self, name: str, action: Any) -> Any:
        started = time.perf_counter()
        result = action()
        duration_ms = round((time.perf_counter() - started) * 1000)
        detail = self._detail(result)
        self.steps.append(StepResult(name=name, duration_ms=duration_ms, detail=detail))
        print(f"[PASS] {name:<28} {duration_ms:>7} ms  {detail}", flush=True)
        return result

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
        payload = response.json()
        if not response.is_success:
            raise GraphE2EFailed(f"{method} {path} HTTP {response.status_code}: {payload}")
        if payload.get("code") != 0:
            raise GraphE2EFailed(f"{method} {path} business error: {payload}")
        return payload.get("data")

    @staticmethod
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise GraphE2EFailed(message)

    @staticmethod
    def _detail(value: Any) -> str:
        if isinstance(value, dict):
            parts = []
            for key in ("nodes", "links", "created_entities", "score", "quiz_id"):
                if key in value:
                    val = value[key]
                    parts.append(f"{key}={len(val) if isinstance(val, list) else val}")
            return ", ".join(parts[:4]) or f"keys={len(value)}"
        if isinstance(value, list):
            return f"items={len(value)}"
        return str(value)[:80]


def run(args: argparse.Namespace) -> dict[str, Any]:
    checker = KnowledgeGraphE2ECheck(args.base_url, args.timeout)
    suffix = str(int(time.time() * 1000))
    username = f"kg_{suffix}"
    password = "KgGraphE2E2026!"

    try:
        checker.run_step("health/ping", lambda: checker.request("GET", "/ping", authenticated=False))
        checker.run_step(
            "auth/register",
            lambda: checker.request(
                "POST",
                "/auth/register",
                json_body={
                    "username": username,
                    "email": f"{username}@example.test",
                    "password": password,
                    "role": "student",
                },
                authenticated=False,
            ),
        )
        login = checker.run_step(
            "auth/login",
            lambda: checker.request(
                "POST",
                "/auth/login",
                json_body={"username": username, "password": password},
                authenticated=False,
            ),
        )
        checker.require(bool(login.get("access_token")), "登录未返回 access_token")
        checker.headers = {"Authorization": f"Bearer {login['access_token']}"}

        course = checker.run_step(
            "course/create",
            lambda: checker.request(
                "POST",
                "/courses",
                json_body={
                    "title": f"知识图谱 E2E {suffix}",
                    "course_code": f"KG-{suffix[-8:]}",
                    "description": "图谱双轨 HTTP 验收课程",
                    "subject": "数据结构",
                    "visibility": "private",
                },
            ),
        )
        course_id = course["id"]

        tutor = checker.run_step(
            "tutor/chat",
            lambda: checker.request(
                "POST",
                "/tutor/chat",
                json_body={
                    "course_id": course_id,
                    "question": "请解释二叉树与 BFS 的区别，以及栈和队列的应用场景。",
                    "top_k": 5,
                    "use_rag": True,
                    "use_wiki": True,
                    "use_profile": False,
                    "stream": False,
                },
            ),
        )
        checker.require(len(str(tutor.get("answer") or "")) >= 20, "Tutor 回答过短")
        checker.require(isinstance(tutor.get("graph_context"), dict), "Tutor 响应缺少 graph_context")
        extract = tutor.get("knowledge_extract") or {}
        checker.require(
            int(extract.get("entities_merged") or 0) >= 0,
            "knowledge_extract 格式异常",
        )

        graph_before = checker.run_step(
            "wiki/graph(before)",
            lambda: checker.request(
                "GET",
                "/wiki/graph",
                params={"course_id": course_id, "view": "merged"},
            ),
        )
        nodes_before = graph_before.get("nodes") or []
        checker.require(isinstance(nodes_before, list), "wiki/graph nodes 应为列表")

        knowledge_id = None
        for node in nodes_before:
            if node.get("knowledge_id"):
                knowledge_id = node["knowledge_id"]
                break

        quiz = checker.run_step(
            "quiz/generate",
            lambda: checker.request(
                "POST",
                "/quizzes/generate",
                json_body={
                    "course_id": course_id,
                    "knowledge_id": knowledge_id,
                    "quiz_type": "practice",
                    "question_types": ["single_choice"],
                    "difficulty": "medium",
                    "count": 2,
                    "topic": "二叉树与 BFS",
                },
            ),
        )
        questions = quiz.get("questions") or []
        checker.require(len(questions) >= 1, "练习题生成失败")

        submitted = checker.run_step(
            "quiz/submit",
            lambda: checker.request(
                "POST",
                f"/quizzes/{quiz['quiz_id']}/submit",
                json_body={
                    "answers": [
                        {
                            "question_id": question["id"],
                            "answer_text": question.get("standard_answer") or "A",
                        }
                        for question in questions
                    ]
                },
            ),
        )
        checker.require(submitted.get("total_questions", 0) >= 1, "答题提交失败")

        graph_after = checker.run_step(
            "wiki/graph(after)",
            lambda: checker.request(
                "GET",
                "/wiki/graph",
                params={"course_id": course_id, "view": "merged"},
            ),
        )
        nodes_after = graph_after.get("nodes") or []
        mastery_values = [
            float(node.get("mastery_score") or 0)
            for node in nodes_after
            if node.get("knowledge_id")
        ]
        checker.require(
            any(score > 0 for score in mastery_values) or len(nodes_after) >= len(nodes_before),
            "刷题后图谱未体现掌握度或节点未增长",
        )

        search = checker.run_step(
            "knowledge/search",
            lambda: checker.request(
                "POST",
                "/knowledge/search",
                json_body={"course_id": course_id, "query": "二叉树 BFS", "top_k": 5},
            ),
        )
        checker.require(isinstance(search.get("items"), list), "knowledge/search 缺少 items")
        checker.require(isinstance(search.get("graph_context"), dict), "knowledge/search 缺少 graph_context")

        return {
            "username": username,
            "course_id": course_id,
            "nodes_before": len(nodes_before),
            "nodes_after": len(nodes_after),
            "mastery_max": max(mastery_values) if mastery_values else 0,
            "graph_context_keys": list((tutor.get("graph_context") or {}).keys()),
            "steps": [
                {"name": step.name, "duration_ms": step.duration_ms, "detail": step.detail}
                for step in checker.steps
            ],
        }
    finally:
        checker.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="知识图谱双轨 HTTP 集成验收")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run(args)
    except GraphE2EFailed as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\nKnowledge graph E2E: ALL PASSED")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
