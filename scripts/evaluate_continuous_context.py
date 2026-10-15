"""Real HTTP regression for shared conversation state. Creates isolated evaluation data.

Checks persistence and deterministic invariants; does not replace blind answer grading.
No API keys, passwords or bearer tokens are written to the report.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def scenarios() -> list[dict]:
    topics = [("栈", "队列"), ("二叉树", "二叉搜索树"), ("链表", "数组"),
              ("广度优先搜索", "深度优先搜索"), ("快速排序", "归并排序"), ("哈希表", "二叉搜索树")]
    result = []
    for category in ("fast", "agent", "mixed", "reload", "boundary"):
        for index, (topic, other) in enumerate(topics):
            turns = [f"后续用中文，简短回答。请解释{topic}的核心特点。",
                     "接着说刚才这个知识点的时间复杂度。", f"它和{other}有什么区别？", "请总结我们刚才讨论的两个知识点。"]
            result.append({"id": f"{category}_{index+1}", "category": category, "topic": topic, "turns": turns})
    return result


class Evaluation:
    def __init__(self, base: str, output: Path, concurrency: int, resume_from: Path | None = None):
        self.base, self.output = base.rstrip("/"), output
        self.limit = asyncio.Semaphore(concurrency)
        self.report = {"started_at": datetime.now(UTC).isoformat(), "checks": "HTTP persistence, source identity, request replay and conservative topic heuristics; not blind semantic grading", "results": []}
        if resume_from:
            previous = json.loads(resume_from.read_text(encoding="utf-8"))
            self.report["previous_attempts"] = previous
            self.report["results"] = [item for item in previous.get("results", []) if item.get("passed")]

    async def request(self, client, method, path, payload=None):
        response = await client.request(method, self.base + "/api/v1" + path, json=payload)
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(str(body.get("message")))
        return body["data"]

    def save(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.output)

    async def turn(self, client, conversation, question, mode, replay=False):
        request_id = str(uuid4())
        start = time.monotonic()
        if mode == "fast":
            payload = {"course_id": self.course, "conversation_id": conversation, "client_request_id": request_id,
                       "question": question, "use_rag": False, "use_wiki": False, "use_profile": True, "stream": False}
            result = await self.request(client, "POST", "/tutor/chat", payload)
            if result.get("fallback_used") or result.get("provider") == "mock":
                raise AssertionError("Real model evaluation unexpectedly used fallback")
            assert result.get("model") == self.report["configured_model"], "Server model differs from evaluation configuration"
            if replay:
                duplicate = await self.request(client, "POST", "/tutor/chat", payload)
                assert duplicate["message_id"] == result["message_id"], "Replay created a different message"
            return {"mode": mode, "question": question, "answer": result["answer"], "model": result.get("model"),
                    "message_id": result["message_id"], "seconds": round(time.monotonic()-start, 2)}
        payload = {"content": question, "client_request_id": request_id}
        accepted = await self.request(client, "POST", f"/agent/conversations/{conversation}/messages", payload)
        task_id = accepted["task"]["id"]
        if replay:
            duplicate = await self.request(client, "POST", f"/agent/conversations/{conversation}/messages", payload)
            assert duplicate["task"]["id"] == task_id, "Replay created a different task"
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            task = await self.request(client, "GET", f"/agent/tasks/{task_id}")
            if task["status"] in {"succeeded", "failed", "cancelled", "waiting_confirmation"}:
                if task["status"] != "succeeded":
                    raise AssertionError(f"Agent {task['status']}: {task.get('error_message')}")
                messages = (await self.request(client, "GET", f"/agent/conversations/{conversation}/messages?limit=100"))["items"]
                message = next((item for item in reversed(messages) if item["role"] == "assistant" and item.get("task_id") == task_id), None)
                assert message is not None, "Completed task missing its own persisted answer"
                answer = message["content"]
                metadata = message.get("payload") or {}
                assert not metadata.get("fallback_used") and metadata.get("provider") != "mock", "Agent answer used fallback"
                assert metadata.get("model") == self.report["configured_model"], "Agent answer model differs from evaluation configuration"
                assert answer, "Completed task missing persisted answer"
                return {"mode": mode, "question": question, "answer": answer, "task_id": task_id,
                        "model": metadata.get("model"), "intent": task.get("input_payload", {}).get("intent_frame_v1"), "seconds": round(time.monotonic()-start, 2)}
            await asyncio.sleep(0.5)
        await self.request(client, "POST", f"/agent/tasks/{task_id}/cancel")
        raise TimeoutError("Agent exceeded 240 seconds and was cancelled")

    async def run_one(self, item):
        async with self.limit:
            record = {"id": item["id"], "category": item["category"], "turns": [], "passed": False}
            try:
                async with httpx.AsyncClient(headers=self.headers, timeout=240) as client:
                    conversation = (await self.request(client, "POST", "/agent/conversations", {"course_id": self.course, "title": "连续上下文评测 " + item["id"]}))["id"]
                    record["conversation_id"] = conversation
                    for index, question in enumerate(item["turns"]):
                        category = item["category"]
                        mode = "agent" if category == "agent" or category in {"mixed", "boundary"} and index % 2 else "fast"
                        if category == "reload":
                            history = await self.request(client, "GET", f"/agent/conversations/{conversation}/messages?limit=100")
                            assert len(history["items"]) == index*2
                        record["turns"].append(await self.turn(client, conversation, question, mode, replay=index == 0))
                    messages = (await self.request(client, "GET", f"/agent/conversations/{conversation}/messages?limit=100"))["items"]
                    assert len(messages) == len(item["turns"])*2, "Missing or duplicated persisted turns"
                    aliases = {"广度优先搜索": "BFS", "深度优先搜索": "DFS"}
                    last_answer = record["turns"][-1]["answer"]
                    assert item["topic"] in last_answer or aliases.get(item["topic"], item["topic"]) in last_answer, "Final summary omitted the explicit opening topic"
                    if category == "boundary":
                        fresh = (await self.request(client, "POST", "/agent/conversations", {"course_id": self.course}))["id"]
                        assert not (await self.request(client, "GET", f"/agent/conversations/{fresh}/messages"))["items"], "New conversation inherited raw history"
                    record["passed"] = True
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            self.report["results"].append(record)
            self.save()
            print(f"{record['id']}: {'PASS' if record['passed'] else record.get('error')}", flush=True)

    async def run(self, maximum: int, long_count: int):
        from app.core.config import settings
        assert settings.llm_api_key and settings.llm_provider != "mock", "Real Provider configuration required"
        self.report["configured_model"] = settings.llm_model_name
        previous = self.report.get("previous_attempts")
        if previous:
            assert previous.get("configured_model") == settings.llm_model_name, "Cannot resume evidence from a different model"
            assert all(turn.get("model") == settings.llm_model_name for item in self.report["results"] for turn in item.get("turns", [])), "Cannot resume evidence without verified model identity"
        async with httpx.AsyncClient(timeout=60) as client:
            username = "context_eval_" + uuid4().hex[:12]
            password = secrets.token_urlsafe(24)
            await self.request(client, "POST", "/auth/register", {"username": username, "password": password})
            login = await self.request(client, "POST", "/auth/login", {"username": username, "password": password})
            self.headers = {"Authorization": "Bearer " + login["access_token"]}
            client.headers.update(self.headers)
            self.report["evaluation_user_id"] = login["user"]["id"]
            self.course = (await self.request(client, "POST", "/courses", {"title": "连续上下文验收专用课程", "subject": "数据结构"}))["id"]
            self.report["evaluation_course_id"] = self.course
        items = scenarios()[:maximum]
        for index in range(long_count):
            topic = ["栈", "二叉树", "哈希表"][index]
            turns = [f"后续用中文，简短回答。我正在学习{topic}，这是本次讨论的主题。请先说核心特点。"]
            for number in range(29):
                turns.append(f"仍然围绕{topic}，请简短解释其" + ["典型应用。", "常见误区。", "操作复杂度。", "实现注意点。", "优缺点。"][number % 5])
            turns.append("现在请回顾本次对话最开始确定的学习主题，并概括我们的讨论。")
            items.append({"id": f"long_{index+1}", "category": "long", "topic": topic, "turns": turns})
        completed_ids = {item["id"] for item in self.report["results"]}
        await asyncio.gather(*(self.run_one(item) for item in items if item["id"] not in completed_ids))
        self.report.update(finished_at=datetime.now(UTC).isoformat(), passed=sum(item["passed"] for item in self.report["results"]), total=len(items))
        self.save()
        return self.report["passed"] == len(items)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8011")
    parser.add_argument("--output", type=Path, default=ROOT / "data/seed_knowledge/data_structure/eval/baselines/continuous_context_real.json")
    parser.add_argument("--max-scenarios", type=int, default=30)
    parser.add_argument("--long-count", type=int, default=3, choices=range(4))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args()
    evaluation = Evaluation(args.base_url, args.output, args.concurrency, args.resume_from)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(0 if asyncio.run(evaluation.run(args.max_scenarios, args.long_count)) else 1)
