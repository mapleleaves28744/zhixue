#!/usr/bin/env python3
"""为已有课程回填 Wiki↔知识点绑定、知识点关系边与图谱掌握度展示。

用法（需本地后端已启动）:
  python scripts/backfill_course_graph.py --username stu_01 --course-code STU01-LONGTERM
"""

from __future__ import annotations

import argparse
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="stu_01")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--course-code", default="STU01-LONGTERM")
    parser.add_argument("--base-url", default=BASE)
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=httpx.Timeout(360.0))
    try:
        ping = client.get("/ping")
        if ping.status_code != 200:
            print("后端未响应，请先启动 uvicorn", file=sys.stderr)
            return 1
    except httpx.ConnectError:
        print("无法连接后端，请先启动 uvicorn", file=sys.stderr)
        return 1

    login = client.post("/auth/login", json={"username": args.username, "password": args.password}).json()
    if login.get("code") != 0:
        print("登录失败:", login, file=sys.stderr)
        return 1
    headers = {"Authorization": f"Bearer {login['data']['access_token']}"}

    courses = client.get("/courses", params={"page": 1, "page_size": 50}, headers=headers).json()["data"]
    course = next((c for c in courses.get("items") or [] if c.get("course_code") == args.course_code), None)
    if not course:
        print(f"未找到课程 {args.course_code}", file=sys.stderr)
        return 1
    course_id = course["id"]
    print(f"course_id={course_id} title={course.get('title')}")

    materials = client.get(
        "/materials",
        params={"course_id": course_id, "page": 1, "page_size": 100},
        headers=headers,
    ).json()["data"].get("items") or []
    total_relations = 0
    for mat in materials:
        mid = mat["id"]
        resp = client.post("/knowledge/extract-from-material", json={"material_id": mid}, headers=headers).json()
        if resp.get("code") != 0:
            print(f"  extract {mat.get('file_name')}: FAIL {resp.get('message')}")
            continue
        rel = int((resp.get("data") or {}).get("relations_created") or 0)
        total_relations += rel
        print(f"  extract {mat.get('file_name')}: points={resp['data'].get('extracted_count')} relations+={rel}")

    graph = client.get("/wiki/graph", params={"course_id": course_id, "view": "merged"}, headers=headers).json()
    if graph.get("code") != 0:
        print("图谱读取失败:", graph, file=sys.stderr)
        return 1
    data = graph["data"]
    nodes = data.get("nodes") or []
    links = data.get("links") or []
    mastery = [float(n.get("mastery_score") or 0) for n in nodes]
    bound = sum(1 for n in nodes if n.get("knowledge_id"))
    print(
        f"完成: nodes={len(nodes)} links={len(links)} "
        f"knowledge_bound={bound} relations_inferred_session={total_relations} "
        f"mastery_max={max(mastery) if mastery else 0:.1%} mastery_avg={sum(mastery)/len(mastery) if mastery else 0:.1%}"
    )
    if not links:
        print("提示: 若仍无边，请确认课程内至少有 2 个知识点且已上传/解析资料。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
