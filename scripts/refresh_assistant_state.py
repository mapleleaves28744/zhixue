#!/usr/bin/env python3
"""刷新并验证：后端健康、资源列表、思维导图生成。"""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
USER = "stu_01"
PASSWORD = "123456"
LONGTERM_CODE = "STU01-LONGTERM"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(180.0))

    ping = client.get("/ping")
    print(f"[ping] {ping.status_code}")

    login = client.post("/auth/login", json={"username": USER, "password": PASSWORD}).json()
    if login.get("code") != 0:
        print("登录失败:", login, file=sys.stderr)
        return 1
    headers = {"Authorization": f"Bearer {login['data']['access_token']}"}

    courses = client.get("/courses", params={"page": 1, "page_size": 50}, headers=headers).json()["data"]["items"]
    course = next((c for c in courses if c.get("course_code") == LONGTERM_CODE), courses[0] if courses else None)
    if not course:
        print("无可用课程", file=sys.stderr)
        return 1
    course_id = course["id"]
    print(f"[course] {course.get('title')} ({course.get('course_code')}) id={course_id}")

    all_res = client.get("/resources", params={"page": 1, "page_size": 20, "status": "all"}, headers=headers).json()
    print(f"[resources all] total={all_res['data']['total']}")

    course_res = client.get(
        "/resources",
        params={"course_id": course_id, "page": 1, "page_size": 20, "status": "all"},
        headers=headers,
    ).json()
    print(f"[resources course] total={course_res['data']['total']}")

    gen = client.post(
        "/resources/generate",
        headers=headers,
        json={
            "course_id": course_id,
            "resource_type": "mindmap",
            "requirement": "队列知识点思维导图，用于刷新验证",
            "use_profile": True,
        },
    ).json()
    if gen.get("code") != 0:
        print("[mindmap generate] FAIL:", gen.get("message"), file=sys.stderr)
        return 1
    data = gen.get("data") or {}
    print(
        "[mindmap generate] OK",
        f"id={data.get('id')}",
        f"preview_mode={data.get('preview_mode')}",
        f"media={data.get('media_asset_id')}",
    )

    after = client.get(
        "/resources",
        params={"course_id": course_id, "page": 1, "page_size": 20, "status": "all"},
        headers=headers,
    ).json()
    print(f"[resources after] total={after['data']['total']}")
    print("刷新验证完成。请在浏览器 Ctrl+F5 硬刷新 AI Tutor 页面。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
