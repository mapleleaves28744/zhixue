"""Live API smoke test: mock multimodal -> Mermaid knowledge card fallback."""

from __future__ import annotations

import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def api(client: httpx.Client, method: str, path: str, **kwargs) -> dict:
    response = client.request(method, BASE + path, **kwargs)
    body = response.json()
    if response.status_code >= 400 or body.get("code") != 0:
        raise RuntimeError(f"{method} {path} failed: HTTP {response.status_code} {body}")
    return body["data"]


def main() -> int:
    uname = f"kcard_{uuid.uuid4().hex[:8]}"
    password = "Test123456!"

    with httpx.Client(timeout=120.0) as client:
        print("[1/4] register + login")
        api(
            client,
            "POST",
            "/auth/register",
            json={
                "username": uname,
                "email": f"{uname}@test.local",
                "password": password,
                "display_name": "kcard-test",
            },
        )
        login = api(client, "POST", "/auth/login", json={"username": uname, "password": password})
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        print("[2/4] create course")
        course_id = api(
            client,
            "POST",
            "/courses",
            headers=headers,
            json={"title": "知识卡片测试课", "description": "integration"},
        )["id"]

        print("[3/4] POST /multimodal/images/generate")
        img = api(
            client,
            "POST",
            "/multimodal/images/generate",
            headers=headers,
            json={
                "course_id": course_id,
                "topic": "BFS 广度优先搜索",
                "image_type": "concept_illustration",
                "requirement": "简明知识卡片，标注队列进出",
            },
        )
        mode = img.get("generation_mode")
        print(f"      generation_mode: {mode}")
        print(f"      fallback_reason: {img.get('fallback_reason', 'n/a')}")

        if mode in {"mermaid_mindmap", "mermaid_diagram"}:
            print("[4/4] GET /resources/{id} (Mermaid fallback path)")
            resource = api(client, "GET", f"/resources/{img['resource_id']}", headers=headers)
            content = resource.get("content") or ""
            print(f"      resource_type: {resource.get('resource_type')}")
            preview = content[:120].replace("\n", " / ")
            print(f"      mermaid preview: {preview}")
            if "mindmap" not in content and "flowchart" not in content:
                raise RuntimeError(f"resource content is not mermaid: {content[:200]}")
            print("PASS: Mermaid knowledge card fallback path verified")
            return 0

        if mode == "image":
            print("[4/4] image asset path (real multimodal provider)")
            print(f"      asset_id: {img.get('asset_id')}")
            print(f"      file_url: {img.get('file_url')}")
            print(f"      mime_type: {img.get('mime_type')}")
            if not img.get("file_url"):
                raise RuntimeError(f"missing file_url for image result: {img}")
            print("PASS: real text-to-image knowledge card path verified")
            return 0

        raise RuntimeError(f"unexpected generation_mode: {img}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
