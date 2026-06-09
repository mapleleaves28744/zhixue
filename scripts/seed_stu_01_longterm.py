#!/usr/bin/env python3
"""为长期演示账号 stu_01 积累学习闭环数据（资料、Wiki、答疑、刷题、画像、记忆、自进化）。

默认账号：stu_01 / 123456
用法：
  python scripts/seed_stu_01_longterm.py
  python scripts/seed_stu_01_longterm.py --base-url http://127.0.0.1:8000/api/v1 --skip-agent
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_USERNAME = "stu_01"
DEFAULT_PASSWORD = "123456"
DEFAULT_EMAIL = "stu_01@zhixue.test"
COURSE_CODE = "STU01-LONGTERM"
COURSE_TITLE = "数据结构长期测试课"

MATERIAL_FILES = [
    REPO_ROOT / "data/数据结构知识库/01_课程体系与教学大纲/数据结构课程教学大纲.md",
    REPO_ROOT / "data/数据结构知识库/02_LLMWiki知识页/02_线性表.md",
    REPO_ROOT / "data/数据结构知识库/02_LLMWiki知识页/03_栈与队列.md",
]

TUTOR_QUESTIONS = [
    "线性表和链表有什么区别？我更适合先学哪一种？",
    "请用通俗例子解释栈在函数调用中的作用。",
    "循环队列为什么要牺牲一个存储单元来判断队满？",
    "二叉树前序和中序遍历有什么区别？给我一个小例子。",
    "我最近图和排序都不太会，帮我列一个三天的复习计划。",
    "BFS 和 DFS 分别适合解决什么问题？",
]

PROFILE_DIALOGUE = (
    "我是计算机专业大二学生 stu_01，目标期末数据结构 85 分以上。"
    "递归、树和图算法比较薄弱，做题容易漏边界条件。"
    "我喜欢 Python 代码示例、分步骤讲解，总结不要太长。"
)

AGENT_PLAN_MESSAGE = "根据我的薄弱点，为我生成接下来三天的数据结构学习计划，并推荐练习。"

TERMINAL_TASK_STATUSES = {"succeeded", "failed", "cancelled", "waiting_confirmation"}


class SeedFailed(RuntimeError):
    pass


@dataclass
class SeedSummary:
    username: str
    password: str
    user_id: str | None = None
    course_id: str | None = None
    materials: list[dict[str, Any]] = field(default_factory=list)
    wiki_pages: int = 0
    tutor_chats: int = 0
    quizzes_submitted: int = 0
    mistakes: int = 0
    graph_nodes: int = 0
    graph_links: int = 0
    mastery_max: float = 0.0
    profile_keys: list[str] = field(default_factory=list)
    memories: int = 0
    evolution_strategies: int = 0
    recommendations: int = 0
    agent_tasks: int = 0
    errors: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


class Stu01Seeder:
    def __init__(self, base_url: str, timeout: float, poll_interval: float) -> None:
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
        )
        self.poll_interval = poll_interval
        self.task_timeout = timeout
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
            raise SeedFailed(f"{method} {path} 非 JSON 响应 HTTP {response.status_code}") from exc
        if not response.is_success or payload.get("code") != 0:
            raise SeedFailed(f"{method} {path} 失败: HTTP {response.status_code}, {payload}")
        return payload.get("data")

    def step(self, summary: SeedSummary, name: str, action: Any) -> Any:
        started = time.perf_counter()
        try:
            result = action()
            detail = _detail(result)
            summary.steps.append({"name": name, "ok": True, "detail": detail, "ms": _ms(started)})
            print(f"[OK]   {name:<32} {detail}", flush=True)
            return result
        except Exception as exc:  # noqa: BLE001 — 批量播种需记录并继续
            msg = str(exc)
            summary.errors.append(f"{name}: {msg}")
            summary.steps.append({"name": name, "ok": False, "detail": msg, "ms": _ms(started)})
            print(f"[WARN] {name:<32} {msg}", flush=True)
            return None

    def ensure_account(self, summary: SeedSummary, username: str, password: str, email: str) -> dict[str, Any]:
        self.step(
            summary,
            "health/ping",
            lambda: self.request("GET", "/ping", authenticated=False),
        )
        try:
            self.request(
                "POST",
                "/auth/register",
                json_body={
                    "username": username,
                    "email": email,
                    "password": password,
                    "role": "student",
                },
                authenticated=False,
            )
            print(f"[INFO] 已注册新账号 {username}", flush=True)
        except SeedFailed:
            print(f"[INFO] 账号 {username} 已存在，直接登录", flush=True)
        login = self.step(
            summary,
            "auth/login",
            lambda: self.request(
                "POST",
                "/auth/login",
                json_body={"username": username, "password": password},
                authenticated=False,
            ),
        )
        if not login or not login.get("access_token"):
            raise SeedFailed("登录失败")
        self.headers = {"Authorization": f"Bearer {login['access_token']}"}
        summary.user_id = login.get("user", {}).get("id")
        return login

    def ensure_course(self, summary: SeedSummary) -> str:
        page = self.request("GET", "/courses", params={"page": 1, "page_size": 50})
        for item in page.get("items") or []:
            if item.get("course_code") == COURSE_CODE:
                summary.course_id = item["id"]
                print(f"[INFO] 复用已有课程 {COURSE_TITLE} ({summary.course_id})", flush=True)
                return summary.course_id
        course = self.step(
            summary,
            "course/create",
            lambda: self.request(
                "POST",
                "/courses",
                json_body={
                    "title": COURSE_TITLE,
                    "course_code": COURSE_CODE,
                    "description": "stu_01 长期测试专用课程，用于积累画像、记忆、掌握度与 Wiki 图谱。",
                    "subject": "数据结构",
                    "visibility": "private",
                },
            ),
        )
        if not course:
            raise SeedFailed("无法创建课程")
        summary.course_id = course["id"]
        return summary.course_id

    def upload_and_pipeline_material(
        self,
        summary: SeedSummary,
        course_id: str,
        file_path: Path,
    ) -> dict[str, Any] | None:
        if not file_path.is_file():
            summary.errors.append(f"material missing: {file_path}")
            print(f"[WARN] 资料不存在，跳过: {file_path}", flush=True)
            return None
        content = file_path.read_bytes()
        material = self.step(
            summary,
            f"upload/{file_path.name[:24]}",
            lambda: self.request(
                "POST",
                "/materials/upload",
                data={"course_id": course_id},
                files={"file": (file_path.name, content, "text/markdown")},
            ),
        )
        if not material:
            return None
        material_id = material["id"]
        self.step(summary, f"parse/{material_id[:8]}", lambda: self.request("POST", f"/materials/{material_id}/parse"))
        self.step(summary, f"chunk/{material_id[:8]}", lambda: self.request("POST", f"/materials/{material_id}/chunk"))
        self.step(summary, f"embed/{material_id[:8]}", lambda: self.request("POST", f"/materials/{material_id}/embed"))
        extract = self.step(
            summary,
            f"extract/{material_id[:8]}",
            lambda: self.request(
                "POST",
                "/knowledge/extract-from-material",
                json_body={"material_id": material_id},
            ),
        )
        wiki = self.step(
            summary,
            f"wiki-gen/{material_id[:8]}",
            lambda: self.request(
                "POST",
                "/wiki/pages/generate-from-material",
                json_body={"course_id": course_id, "material_id": material_id},
            ),
        )
        record = {
            "id": material_id,
            "name": file_path.name,
            "extracted": int((extract or {}).get("extracted_count") or 0),
            "wiki_generated": int((wiki or {}).get("generated_count") or 0),
        }
        summary.materials.append(record)
        return record

    def run_tutor_round(self, summary: SeedSummary, course_id: str, question: str, wiki_page_id: str | None) -> None:
        payload: dict[str, Any] = {
            "course_id": course_id,
            "question": question,
            "top_k": 5,
            "use_rag": True,
            "use_wiki": True,
            "use_profile": True,
            "stream": False,
        }
        if wiki_page_id:
            payload["wiki_page_id"] = wiki_page_id
        result = self.step(
            summary,
            f"tutor/{question[:18]}",
            lambda: self.request("POST", "/tutor/chat", json_body=payload),
        )
        if result and len(str(result.get("answer") or "")) >= 20:
            summary.tutor_chats += 1

    def submit_quiz(
        self,
        summary: SeedSummary,
        course_id: str,
        knowledge_id: str | None,
        *,
        topic: str,
        intentional_wrong: bool,
    ) -> None:
        quiz = self.step(
            summary,
            f"quiz-gen/{topic[:12]}",
            lambda: self.request(
                "POST",
                "/quizzes/generate",
                json_body={
                    "course_id": course_id,
                    "knowledge_id": knowledge_id,
                    "quiz_type": "practice",
                    "question_types": ["single_choice", "true_false"],
                    "difficulty": "medium",
                    "count": 3,
                    "topic": topic,
                },
            ),
        )
        if not quiz or not quiz.get("quiz_id"):
            return
        answers = []
        for question in quiz.get("questions") or []:
            if intentional_wrong:
                answers.append({"question_id": question["id"], "answer_text": "__stu01_wrong__"})
            else:
                answers.append(
                    {
                        "question_id": question["id"],
                        "answer_text": question.get("standard_answer") or "A",
                    }
                )
        submitted = self.step(
            summary,
            f"quiz-submit/{topic[:10]}",
            lambda: self.request(
                "POST",
                f"/quizzes/{quiz['quiz_id']}/submit",
                json_body={"answers": answers},
            ),
        )
        if submitted:
            summary.quizzes_submitted += 1
            summary.mistakes += len(submitted.get("mistakes") or [])

    def wait_agent_task(self, task_id: str) -> dict[str, Any] | None:
        deadline = time.monotonic() + self.task_timeout
        last_status = "unknown"
        while time.monotonic() < deadline:
            task = self.request("GET", f"/agent/tasks/{task_id}")
            last_status = str(task.get("status") or "unknown")
            if last_status in TERMINAL_TASK_STATUSES:
                return task
            time.sleep(self.poll_interval)
        raise SeedFailed(f"Agent 任务超时 task={task_id} last={last_status}")

    def run_agent_dialogue(self, summary: SeedSummary, course_id: str) -> None:
        conversation = self.step(
            summary,
            "agent/conversation",
            lambda: self.request(
                "POST",
                "/agent/conversations",
                json_body={"course_id": course_id, "title": "stu_01 长期测试对话"},
            ),
        )
        if not conversation:
            return
        conv_id = conversation["id"]
        for idx, content in enumerate([PROFILE_DIALOGUE, AGENT_PLAN_MESSAGE], start=1):
            accepted = self.step(
                summary,
                f"agent/msg-{idx}",
                lambda c=content: self.request(
                    "POST",
                    f"/agent/conversations/{conv_id}/messages",
                    json_body={"content": c},
                ),
            )
            if not accepted or not accepted.get("task"):
                continue
            task_id = accepted["task"]["id"]
            try:
                task = self.wait_agent_task(task_id)
                if task and task.get("status") == "succeeded":
                    summary.agent_tasks += 1
            except SeedFailed as exc:
                summary.errors.append(str(exc))

    def collect_metrics(self, summary: SeedSummary, course_id: str) -> None:
        wiki = self.request(
            "GET",
            "/wiki/pages",
            params={"course_id": course_id, "page": 1, "page_size": 100},
        )
        summary.wiki_pages = int(wiki.get("total") or len(wiki.get("items") or []))

        graph = self.request(
            "GET",
            "/wiki/graph",
            params={"course_id": course_id, "view": "merged"},
        )
        nodes = graph.get("nodes") or []
        summary.graph_nodes = len(nodes)
        summary.graph_links = len(graph.get("links") or [])
        mastery_values = [float(n.get("mastery_score") or 0) for n in nodes if n.get("knowledge_id")]
        summary.mastery_max = max(mastery_values) if mastery_values else 0.0

        profile = self.request("GET", "/student/profile")
        summary.profile_keys = sorted((profile or {}).keys())

        memories = self.request("GET", "/student/memory")
        summary.memories = len(memories or [])

        recs = self.request(
            "GET",
            "/recommendations",
            params={"course_id": course_id, "page": 1, "page_size": 20},
        )
        summary.recommendations = int(recs.get("total") or len(recs.get("items") or []))


def _detail(value: Any) -> str:
    if isinstance(value, dict):
        parts = []
        for key in (
            "id",
            "generated_count",
            "extracted_count",
            "chunk_count",
            "embedded_count",
            "quiz_id",
            "strategies_count",
            "total",
        ):
            if key in value:
                val = value[key]
                parts.append(f"{key}={len(val) if isinstance(val, list) else val}")
        return ", ".join(parts[:4]) or f"keys={len(value)}"
    if isinstance(value, list):
        return f"items={len(value)}"
    return str(value)[:72]


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def run(args: argparse.Namespace) -> SeedSummary:
    seeder = Stu01Seeder(args.base_url, args.timeout, args.poll_interval)
    summary = SeedSummary(username=args.username, password=args.password)
    try:
        seeder.ensure_account(summary, args.username, args.password, args.email)
        course_id = seeder.ensure_course(summary)

        for file_path in MATERIAL_FILES:
            seeder.upload_and_pipeline_material(summary, course_id, file_path)

        wiki_list = seeder.request(
            "GET",
            "/wiki/pages",
            params={"course_id": course_id, "page": 1, "page_size": 20},
        )
        wiki_items = wiki_list.get("items") or []
        first_wiki_id = wiki_items[0]["id"] if wiki_items else None
        knowledge_id = None
        for page in wiki_items:
            if page.get("knowledge_id"):
                knowledge_id = page["knowledge_id"]
                break

        seeder.step(
            summary,
            "profile/dialogue-ingest",
            lambda: seeder.request(
                "POST",
                "/student/profile/dialogue-ingest",
                json_body={"course_id": course_id, "dialogue_text": PROFILE_DIALOGUE},
            ),
        )

        for question in TUTOR_QUESTIONS:
            seeder.run_tutor_round(summary, course_id, question, first_wiki_id)

        seeder.step(
            summary,
            "resource/summary",
            lambda: seeder.request(
                "POST",
                "/resources/generate",
                json_body={
                    "course_id": course_id,
                    "knowledge_id": knowledge_id,
                    "wiki_page_id": first_wiki_id,
                    "resource_type": "summary",
                    "requirement": "生成包含核心定义、易错点、复习清单的学习总结。",
                    "use_profile": True,
                    "save_to_wiki": False,
                },
            ),
        )
        seeder.step(
            summary,
            "resource/flashcard",
            lambda: seeder.request(
                "POST",
                "/resources/generate",
                json_body={
                    "course_id": course_id,
                    "knowledge_id": knowledge_id,
                    "resource_type": "flashcard",
                    "requirement": "针对栈、队列、线性表生成 5 张复习闪卡。",
                    "use_profile": True,
                    "save_to_wiki": False,
                },
            ),
        )

        seeder.submit_quiz(summary, course_id, knowledge_id, topic="线性表与链表", intentional_wrong=True)
        seeder.submit_quiz(summary, course_id, knowledge_id, topic="栈与循环队列", intentional_wrong=False)
        seeder.submit_quiz(summary, course_id, knowledge_id, topic="树与图遍历", intentional_wrong=True)

        seeder.step(
            summary,
            "diagnosis/analyze",
            lambda: seeder.request(
                "POST",
                "/diagnosis/analyze",
                params={"course_id": course_id, "trigger_evolution": "false"},
            ),
        )
        seeder.step(summary, "profile/rebuild", lambda: seeder.request("POST", "/student/profile/rebuild"))
        seeder.step(summary, "memory/reflect", lambda: seeder.request("POST", "/student/memory/reflect"))
        evolution = seeder.step(
            summary,
            "evolution/analyze",
            lambda: seeder.request(
                "POST",
                "/evolution/analyze",
                json_body={
                    "course_id": course_id,
                    "focus": "基于 stu_01 的错题、答疑与画像，生成下一轮学习策略",
                },
            ),
        )
        if evolution:
            summary.evolution_strategies = int(evolution.get("strategies_count") or 0)
        seeder.step(
            summary,
            "recommendations/refresh",
            lambda: seeder.request("POST", "/recommendations/refresh", params={"course_id": course_id}),
        )
        seeder.step(
            summary,
            "learning-events",
            lambda: seeder.request(
                "POST",
                "/learning-records/events/batch",
                json_body={
                    "events": [
                        {
                            "course_id": course_id,
                            "event_type": "wiki_read",
                            "event_source": "stu_01_seed",
                            "event_payload": {"note": "复习线性表 Wiki"},
                        },
                        {
                            "course_id": course_id,
                            "event_type": "quiz_complete",
                            "event_source": "stu_01_seed",
                            "event_payload": {"note": "完成栈队列练习"},
                        },
                    ]
                },
            ),
        )

        if not args.skip_agent:
            seeder.run_agent_dialogue(summary, course_id)

        seeder.collect_metrics(summary, course_id)
        return summary
    finally:
        seeder.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="stu_01 长期测试账号数据播种")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--skip-agent", action="store_true", help="跳过 LangGraph Agent（无 worker 时）")
    parser.add_argument("--json-output", default=str(REPO_ROOT / "data/stu_01_seed_report.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run(args)
    except SeedFailed as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    report = {
        "login": {"username": summary.username, "password": summary.password},
        "user_id": summary.user_id,
        "course_id": summary.course_id,
        "course_title": COURSE_TITLE,
        "materials": summary.materials,
        "wiki_pages": summary.wiki_pages,
        "tutor_chats": summary.tutor_chats,
        "quizzes_submitted": summary.quizzes_submitted,
        "mistakes": summary.mistakes,
        "graph_nodes": summary.graph_nodes,
        "graph_links": summary.graph_links,
        "mastery_max": summary.mastery_max,
        "profile_keys": summary.profile_keys,
        "memories": summary.memories,
        "evolution_strategies": summary.evolution_strategies,
        "recommendations": summary.recommendations,
        "agent_tasks": summary.agent_tasks,
        "errors": summary.errors,
        "steps": summary.steps,
        "frontend_urls": {
            "login": "http://127.0.0.1:3000/?auth=login",
            "knowledge": f"http://127.0.0.1:3000/knowledge?course_id={summary.course_id}",
            "assistant": f"http://127.0.0.1:3000/assistant?course_id={summary.course_id}",
            "practice": f"http://127.0.0.1:3000/practice?course_id={summary.course_id}",
            "dashboard": "http://127.0.0.1:3000/dashboard",
            "path_profile": "http://127.0.0.1:3000/path-profile",
        },
    }
    out = Path(args.json_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n========== stu_01 长期测试数据播种完成 ==========")
    print(f"账号: {summary.username}  密码: {summary.password}")
    print(f"课程: {COURSE_TITLE}  ({summary.course_id})")
    print(
        f"Wiki {summary.wiki_pages} 页 | 图谱 {summary.graph_nodes} 节点 {summary.graph_links} 关系 | "
        f"掌握度峰值 {summary.mastery_max:.2f}"
    )
    print(
        f"答疑 {summary.tutor_chats} 次 | 刷题 {summary.quizzes_submitted} 套 | 错题 {summary.mistakes} 条 | "
        f"记忆 {summary.memories} 条 | 自进化策略 {summary.evolution_strategies} 条"
    )
    if summary.errors:
        print(f"警告 {len(summary.errors)} 项（见 {out}）")
    print(f"报告: {out}")
    print("下次登录后建议查看：知识库图谱、练习错题、学习路径/画像、仪表盘推荐")
    return 0 if not summary.errors or summary.wiki_pages > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
