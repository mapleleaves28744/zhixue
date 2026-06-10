#!/usr/bin/env python3
"""补全 stu_01 未完成的刷题、诊断与第三份资料（可重复执行）。"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
USERNAME = "stu_01"
PASSWORD = "123456"
COURSE_CODE = "STU01-LONGTERM"
MATERIAL = Path(__file__).resolve().parents[1] / "data/数据结构知识库/02_LLMWiki知识页/03_栈与队列.md"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(360.0))
    login = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD}).json()
    if login.get("code") != 0:
        print("登录失败", login, file=sys.stderr)
        return 1
    headers = {"Authorization": f"Bearer {login['data']['access_token']}"}

    courses = client.get("/courses", params={"page": 1, "page_size": 50}, headers=headers).json()["data"]
    course = next((c for c in courses["items"] if c.get("course_code") == COURSE_CODE), None)
    if not course:
        print("未找到 STU01-LONGTERM 课程", file=sys.stderr)
        return 1
    course_id = course["id"]
    print(f"course_id={course_id}")

    wiki = client.get("/wiki/pages", params={"course_id": course_id, "page": 1, "page_size": 5}, headers=headers).json()["data"]
    knowledge_id = next((p.get("knowledge_id") for p in wiki.get("items") or [] if p.get("knowledge_id")), None)

    if MATERIAL.is_file():
        names = {m.get("file_name") or m.get("original_filename") for m in client.get("/materials", params={"course_id": course_id, "page": 1, "page_size": 50}, headers=headers).json()["data"].get("items", [])}
        if MATERIAL.name not in names:
            with MATERIAL.open("rb") as fh:
                mat = client.post("/materials/upload", data={"course_id": course_id}, files={"file": (MATERIAL.name, fh, "text/markdown")}, headers=headers).json()
            if mat.get("code") == 0:
                mid = mat["data"]["id"]
                for path in (f"/materials/{mid}/parse", f"/materials/{mid}/chunk", f"/materials/{mid}/embed"):
                    client.post(path, headers=headers)
                client.post("/knowledge/extract-from-material", json={"material_id": mid}, headers=headers)
                client.post("/wiki/pages/generate-from-material", json={"course_id": course_id, "material_id": mid}, headers=headers)
                print(f"uploaded {MATERIAL.name}")

    for topic, wrong in [("线性表", True), ("栈与队列", False), ("树与图", True)]:
        time.sleep(2)
        quiz = client.post(
            "/quizzes/generate",
            headers=headers,
            json={
                "course_id": course_id,
                "knowledge_id": knowledge_id,
                "quiz_type": "practice",
                "question_types": ["single_choice"],
                "difficulty": "medium",
                "count": 3,
                "topic": topic,
            },
        ).json()
        if quiz.get("code") != 0:
            print(f"quiz-gen {topic} failed:", quiz.get("message"))
            continue
        q = quiz["data"]
        answers = [
            {"question_id": item["id"], "answer_text": "__wrong__" if wrong else (item.get("standard_answer") or "A")}
            for item in q.get("questions") or []
        ]
        sub = client.post(f"/quizzes/{q['quiz_id']}/submit", headers=headers, json={"answers": answers}).json()
        print(f"quiz {topic}:", sub.get("code"), "mistakes", len((sub.get("data") or {}).get("mistakes") or []))

    diag = client.post("/diagnosis/analyze", headers=headers, params={"course_id": course_id, "trigger_evolution": "true"}).json()
    print("diagnosis:", diag.get("code"), (diag.get("data") or {}).get("id"))

    evo = client.post("/evolution/analyze", headers=headers, json={"course_id": course_id, "focus": "stu_01 错题补全后策略"}).json()
    print("evolution strategies:", (evo.get("data") or {}).get("strategies_count"))

    graph = client.get("/wiki/graph", params={"course_id": course_id, "view": "merged"}, headers=headers).json()["data"]
    mastery = [float(n.get("mastery_score") or 0) for n in graph.get("nodes") or []]
    print(f"graph nodes={len(graph.get('nodes') or [])} mastery_max={max(mastery) if mastery else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
