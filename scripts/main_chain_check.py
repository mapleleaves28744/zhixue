from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx


MATERIAL_TEXT = """数据结构课程资料：线性表、栈与队列

线性表是由同类型数据元素构成的有限序列。顺序表使用连续存储空间，支持按下标随机访问；
链表通过指针连接结点，插入和删除时通常不需要移动大量元素。

栈是一种后进先出的线性结构。入栈操作将元素放到栈顶，出栈操作移除栈顶元素。
栈常用于函数调用、表达式求值和括号匹配。

队列是一种先进先出的线性结构。循环队列通过复用数组空间避免假溢出。
在长度为 n 的数组中，常保留一个空位，并用 (rear + 1) % n == front 判断队满。
"""


class CheckFailed(RuntimeError):
    pass


@dataclass
class StepResult:
    name: str
    duration_ms: int
    detail: str


class MainChainCheck:
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
        print(f"[PASS] {name:<24} {duration_ms:>7} ms  {detail}", flush=True)
        return result

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        response = self.client.request(
            method,
            path,
            json=json_body,
            params=params,
            files=files,
            data=data,
            headers=self.headers if authenticated else None,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise CheckFailed(
                f"{method} {path} returned non-JSON response: HTTP {response.status_code}"
            ) from exc
        if not response.is_success:
            raise CheckFailed(
                f"{method} {path} failed: HTTP {response.status_code}, {payload}"
            )
        if payload.get("code") != 0:
            raise CheckFailed(f"{method} {path} business failure: {payload}")
        return payload.get("data")

    @staticmethod
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise CheckFailed(message)

    @staticmethod
    def _detail(value: Any) -> str:
        if isinstance(value, list):
            return f"items={len(value)}"
        if isinstance(value, dict):
            preferred = (
                "id",
                "material_id",
                "generated_count",
                "extracted_count",
                "chunk_count",
                "embedded_count",
                "quiz_id",
                "score",
                "strategies_count",
                "total",
                "provider",
            )
            parts = [f"{key}={value[key]}" for key in preferred if key in value]
            return ", ".join(parts[:3]) or f"keys={len(value)}"
        return str(value)[:100]


def run(args: argparse.Namespace) -> dict[str, Any]:
    checker = MainChainCheck(args.base_url, args.timeout)
    suffix = str(int(time.time() * 1000))
    username = f"chain_{suffix}"
    password = "ChainCheck2026!"

    try:
        checker.run_step(
            "health/ping",
            lambda: checker.request("GET", "/ping", authenticated=False),
        )
        checker.run_step(
            "register",
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
            "login",
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
                    "title": f"真实 LLM 主链路验收 {suffix}",
                    "course_code": f"CHAIN-{suffix[-8:]}",
                    "description": "用于验证资料到自进化的真实生成链路。",
                    "subject": "数据结构",
                    "visibility": "private",
                },
            ),
        )
        course_id = course["id"]

        material = checker.run_step(
            "material/upload",
            lambda: checker.request(
                "POST",
                "/materials/upload",
                data={"course_id": course_id},
                files={
                    "file": (
                        f"data-structures-{suffix}.txt",
                        MATERIAL_TEXT.encode("utf-8"),
                        "text/plain",
                    )
                },
            ),
        )
        material_id = material["id"]
        parsed = checker.run_step(
            "material/parse",
            lambda: checker.request("POST", f"/materials/{material_id}/parse"),
        )
        checker.require(
            parsed.get("parse_status") == "success" and parsed.get("text_length", 0) >= 100,
            f"资料解析结果异常: parse_status={parsed.get('parse_status')}, text_length={parsed.get('text_length')}",
        )
        chunks = checker.run_step(
            "material/chunk",
            lambda: checker.request("POST", f"/materials/{material_id}/chunk"),
        )
        checker.require(chunks.get("chunk_count", 0) > 0, "资料切片数为 0")
        embeddings = checker.run_step(
            "material/embed",
            lambda: checker.request("POST", f"/materials/{material_id}/embed"),
        )
        checker.require(embeddings.get("embedded_count", 0) > 0, "资料向量化数量为 0")

        knowledge = checker.run_step(
            "knowledge/extract",
            lambda: checker.request(
                "POST",
                "/knowledge/extract-from-material",
                json_body={"material_id": material_id},
            ),
        )
        checker.require(knowledge.get("extracted_count", 0) > 0, "未抽取到知识点")
        knowledge_id = knowledge["points"][0]["id"]
        search = checker.run_step(
            "knowledge/search",
            lambda: checker.request(
                "POST",
                "/knowledge/search",
                json_body={
                    "course_id": course_id,
                    "query": "循环队列如何判断队满",
                    "top_k": 3,
                },
            ),
        )
        checker.require(bool(search), "RAG 检索未返回资料片段")

        generated_wiki = checker.run_step(
            "wiki/generate",
            lambda: checker.request(
                "POST",
                "/wiki/pages/generate-from-material",
                json_body={"course_id": course_id, "material_id": material_id},
            ),
        )
        checker.require(generated_wiki.get("generated_count", 0) > 0, "未生成 Wiki 页面")
        wiki_id = generated_wiki["pages"][0]["id"]
        wiki = checker.run_step(
            "wiki/detail",
            lambda: checker.request("GET", f"/wiki/pages/{wiki_id}"),
        )
        checker.require(len(str(wiki.get("content") or "")) >= 120, "Wiki 内容过短")
        checker.require(bool(wiki.get("sources")), "Wiki 页面缺少来源追溯")
        versions = checker.run_step(
            "wiki/versions",
            lambda: checker.request("GET", f"/wiki/pages/{wiki_id}/versions"),
        )
        checker.require(bool(versions), "Wiki 页面缺少版本记录")

        tutor = checker.run_step(
            "tutor/chat real LLM",
            lambda: checker.request(
                "POST",
                "/tutor/chat",
                json_body={
                    "course_id": course_id,
                    "wiki_page_id": wiki_id,
                    "question": "结合资料解释循环队列判断队满的条件，并说明为什么要保留一个空位。",
                    "top_k": 3,
                    "use_rag": True,
                    "use_wiki": True,
                    "use_profile": True,
                    "stream": False,
                },
            ),
        )
        provider = str(tutor.get("provider") or "").lower()
        checker.require(len(str(tutor.get("answer") or "")) >= 80, "Tutor 回答过短")
        checker.require(bool(tutor.get("citations")), "Tutor 回答缺少引用")
        checker.require(provider not in {"", "mock", "fallback"}, f"Tutor 未使用真实 Provider: {provider!r}")
        checker.require(not tutor.get("fallback_used"), "真实 LLM 调用失败并回退到了 Mock")

        resource = checker.run_step(
            "resource/generate",
            lambda: checker.request(
                "POST",
                "/resources/generate",
                json_body={
                    "course_id": course_id,
                    "knowledge_id": knowledge_id,
                    "wiki_page_id": wiki_id,
                    "resource_type": "summary",
                    "requirement": "生成一份包含核心定义、易错点和复习清单的学习总结。",
                    "use_profile": True,
                    "save_to_wiki": False,
                },
            ),
        )
        checker.require(len(str(resource.get("content") or "")) >= 120, "生成资源内容过短")
        checker.require(bool(resource.get("personalized_reason")), "生成资源缺少个性化理由")

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
                    "count": 3,
                    "topic": "栈与循环队列",
                },
            ),
        )
        checker.require(len(quiz.get("questions") or []) == 3, "练习题数量不符合请求")
        for question in quiz["questions"]:
            checker.require(len(str(question.get("question_text") or "")) >= 8, "练习题题干过短")
            checker.require(bool(question.get("standard_answer")), "练习题缺少标准答案")
        submitted = checker.run_step(
            "quiz/submit",
            lambda: checker.request(
                "POST",
                f"/quizzes/{quiz['quiz_id']}/submit",
                json_body={
                    "answers": [
                        {
                            "question_id": question["id"],
                            "answer_text": "__intentional_wrong_answer__",
                        }
                        for question in quiz["questions"]
                    ]
                },
            ),
        )
        checker.require(submitted.get("total_questions") == 3, "答题记录数量不正确")
        checker.require(bool(submitted.get("mistakes")), "故意错答后未进入错题本")

        diagnosis = checker.run_step(
            "diagnosis/analyze",
            lambda: checker.request(
                "POST",
                "/diagnosis/analyze",
                params={"course_id": course_id, "trigger_evolution": "false"},
            ),
        )
        checker.require(bool(diagnosis.get("id")), "诊断未落库")
        checker.require(bool(diagnosis.get("summary")), "诊断缺少摘要")
        checker.require(bool(diagnosis.get("recommended_actions")), "诊断缺少建议动作")

        profile = checker.run_step(
            "profile/rebuild",
            lambda: checker.request("POST", "/student/profile/rebuild"),
        )
        checker.require(bool(profile.get("id")), "画像重建未落库")
        memories = checker.run_step(
            "memory/reflect",
            lambda: checker.request("POST", "/student/memory/reflect"),
        )
        checker.require(isinstance(memories, list), "记忆反思响应格式错误")

        evolution = checker.run_step(
            "evolution/analyze",
            lambda: checker.request(
                "POST",
                "/evolution/analyze",
                json_body={
                    "course_id": course_id,
                    "focus": "基于本次错题、诊断和画像生成下一轮学习策略",
                },
            ),
        )
        checker.require(evolution.get("strategies_count", 0) > 0, "自进化未生成策略")
        checker.require(
            all(item.get("evidence") for item in evolution.get("strategies", [])),
            "自进化策略缺少证据",
        )
        checker.run_step(
            "recommendation/refresh",
            lambda: checker.request(
                "POST",
                "/recommendations/refresh",
                params={"course_id": course_id},
            ),
        )
        agent_runs = checker.run_step(
            "agent/runs",
            lambda: checker.request(
                "GET",
                "/agents/runs",
                params={"page": 1, "page_size": 100},
            ),
        )
        checker.require(agent_runs.get("total", 0) >= 5, "Agent 调用链日志数量不足")

        return {
            "username": username,
            "course_id": course_id,
            "material_id": material_id,
            "wiki_id": wiki_id,
            "provider": tutor.get("provider"),
            "model": tutor.get("model"),
            "fallback_used": tutor.get("fallback_used"),
            "steps": [
                {
                    "name": step.name,
                    "duration_ms": step.duration_ms,
                    "detail": step.detail,
                }
                for step in checker.steps
            ],
        }
    finally:
        checker.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="智学工坊真实 LLM 后端主链路验收")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api/v1",
        help="API v1 base URL",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="每个 HTTP 请求的超时秒数",
    )
    parser.add_argument("--json-output", help="将验收摘要写入 JSON 文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    try:
        summary = run(args)
    except (CheckFailed, httpx.HTTPError) as exc:
        print(f"\n[FAIL] 主链路验收失败: {exc}", file=sys.stderr)
        return 1

    summary["total_duration_ms"] = round((time.perf_counter() - started) * 1000)
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as output:
            json.dump(summary, output, ensure_ascii=False, indent=2)
    print("\n真实 LLM 主链路验收通过")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
