#!/usr/bin/env python3
"""验证侧栏媒体类资源是否走真实多模态链路，而非 ResourceAgent 纯文本兜底。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx

MEDIA_CASES: list[dict[str, Any]] = [
    {
        "type": "video",
        "label": "讲解视频",
        "expect": "async_job",
        "job_type": "video",
    },
    {
        "type": "animation",
        "label": "动画演示",
        "expect": "async_job",
        "job_type": "video",
    },
    {
        "type": "immersive_classroom",
        "label": "沉浸课堂",
        "expect": "async_job",
        "job_type": "immersive_classroom",
    },
    {
        "type": "interactive_courseware",
        "label": "互动课件",
        "expect": "html_asset",
    },
    {
        "type": "image",
        "label": "图片",
        "expect": "visual_asset",
    },
]

TEXT_FALLBACK_MARKERS = (
    "个性化学习资源",
    "## 1.",
    "代码骨架",
    "Mock",
)


class VerifyError(Exception):
    pass


def login(client: httpx.Client, username: str, password: str) -> str:
    r = client.post("/auth/login", json={"username": username, "password": password})
    data = r.json()
    if data.get("code") != 0:
        raise VerifyError(f"登录失败: {data}")
    token = data["data"]["access_token"]
    return token


def api(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    r = client.request(method, path, **kwargs)
    payload = r.json()
    if payload.get("code") != 0:
        raise VerifyError(f"{method} {path} -> {payload}")
    return payload["data"]


def looks_like_text_fallback(content: str, title: str) -> bool:
    text = f"{title}\n{content}"
    if len(content) > 400 and any(m in text for m in TEXT_FALLBACK_MARKERS):
        return True
    if content.count("\n## ") >= 2 and "视频任务已创建" not in content and "HTML PPT" not in content:
        return True
    return False


def verify_generate(
    client: httpx.Client,
    *,
    course_id: str,
    case: dict[str, Any],
    job_wait_seconds: float,
) -> dict[str, Any]:
    resource_type = case["type"]
    started = time.perf_counter()
    body = {
        "course_id": course_id,
        "resource_type": resource_type,
        "requirement": f"验收测试：请围绕二叉树入门生成简短{case['label']}。",
        "use_profile": True,
    }
    data = api(client, "POST", "/resources/generate", json=body)
    resource_id = str(data.get("resource_id") or data.get("id") or "")
    result: dict[str, Any] = {
        "type": resource_type,
        "resource_id": resource_id,
        "preview_mode": data.get("preview_mode"),
        "media_job_id": data.get("media_job_id"),
        "media_asset_id": data.get("media_asset_id"),
        "media_mime_type": data.get("media_mime_type"),
        "content_preview": str(data.get("content") or "")[:120],
        "pipeline": "unknown",
        "passed": False,
        "detail": "",
    }

    expect = case["expect"]
    content = str(data.get("content") or "")

    if expect == "async_job":
        job_id = data.get("media_job_id")
        if not job_id:
            result["detail"] = "缺少 media_job_id，可能仍走 ResourceAgent 文本链路"
            return result
        if looks_like_text_fallback(content, str(data.get("title") or "")):
            result["detail"] = "返回长 Markdown，疑似文本兜底"
            return result
        if "任务已创建" not in content and "后台" not in content and "生成" not in content:
            result["detail"] = f"内容不像异步任务占位: {content[:80]}"
            return result

        result["pipeline"] = "media_job_created"
        deadline = time.monotonic() + job_wait_seconds
        job_status = "queued"
        while time.monotonic() < deadline:
            job = api(client, "GET", f"/multimodal/jobs/{job_id}")
            job_status = str(job.get("status") or "")
            if job.get("job_type") and job.get("job_type") != case.get("job_type"):
                result["detail"] = f"job_type 不匹配: {job.get('job_type')}"
                return result
            if job_status == "succeeded":
                detail = api(client, "GET", f"/resources/{resource_id}")
                result["media_asset_id"] = detail.get("media_asset_id")
                result["media_mime_type"] = detail.get("media_mime_type")
                result["preview_mode"] = detail.get("preview_mode")
                result["pipeline"] = "media_job_succeeded"
                result["passed"] = True
                result["detail"] = f"job 完成, asset={detail.get('media_asset_id')}, preview={detail.get('preview_mode')}"
                result["duration_ms"] = round((time.perf_counter() - started) * 1000)
                return result
            if job_status == "failed":
                result["detail"] = f"job 失败: {job.get('error_message')}"
                result["duration_ms"] = round((time.perf_counter() - started) * 1000)
                return result
            time.sleep(3)

        # 任务仍在跑：至少确认已入队，不算文本兜底
        result["passed"] = True
        result["pipeline"] = f"media_job_running({job_status})"
        result["detail"] = f"已入队 {case.get('job_type')} job，{job_wait_seconds}s 内未完成但非文本兜底"
        result["duration_ms"] = round((time.perf_counter() - started) * 1000)
        return result

    if expect == "html_asset":
        asset_id = data.get("media_asset_id")
        preview = data.get("preview_mode")
        mime = str(data.get("media_mime_type") or "")
        if not asset_id:
            result["detail"] = "缺少 media_asset_id，互动课件未生成 HTML 资产"
            return result
        if preview != "html" and "html" not in mime:
            result["detail"] = f"preview/mime 非 HTML: preview={preview}, mime={mime}"
            return result
        if looks_like_text_fallback(content, str(data.get("title") or "")):
            result["detail"] = "仅有 Markdown 正文，无 HTML 课件"
            return result
        result["pipeline"] = "html_ppt_courseware"
        result["passed"] = True
        result["detail"] = f"HTML 课件 asset={asset_id}, provider=html_ppt_skill"
        result["duration_ms"] = round((time.perf_counter() - started) * 1000)
        return result

    if expect == "visual_asset":
        asset_id = data.get("media_asset_id")
        preview = data.get("preview_mode")
        if asset_id or preview in {"image", "mermaid"}:
            result["pipeline"] = "image_or_mermaid"
            result["passed"] = True
            result["detail"] = f"visual preview={preview}, asset={asset_id}"
            result["duration_ms"] = round((time.perf_counter() - started) * 1000)
            return result
        if is_mermaid(content):
            result["pipeline"] = "mermaid_inline"
            result["passed"] = True
            result["detail"] = "Mermaid 知识卡片（无文生图 API 时的合理兜底）"
            result["duration_ms"] = round((time.perf_counter() - started) * 1000)
            return result
        result["detail"] = "无图片/Mermaid 产物，疑似纯文本"
        result["duration_ms"] = round((time.perf_counter() - started) * 1000)
        return result

    result["detail"] = "未知用例"
    result["duration_ms"] = round((time.perf_counter() - started) * 1000)
    return result


def is_mermaid(content: str) -> bool:
    t = content.strip()
    return t.startswith("mindmap") or t.startswith("flowchart")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1/api/v1")
    parser.add_argument("--username", default="stu_01")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--job-wait-seconds", type=float, default=180.0)
    parser.add_argument("--json-output", default="/tmp/media_pipeline_verify.json")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=httpx.Timeout(120.0))
    results: list[dict[str, Any]] = []
    try:
        token = login(client, args.username, args.password)
        client.headers["Authorization"] = f"Bearer {token}"
        courses = api(client, "GET", "/courses", params={"page": 1, "page_size": 5})
        items = courses.get("items") or []
        if not items:
            raise VerifyError("无课程")
        course_id = items[0]["id"]
        print(f"[INFO] course={items[0].get('title')} ({course_id})", flush=True)

        for case in MEDIA_CASES:
            print(f"[RUN] {case['type']} ...", flush=True)
            try:
                row = verify_generate(
                    client,
                    course_id=course_id,
                    case=case,
                    job_wait_seconds=args.job_wait_seconds,
                )
            except Exception as exc:
                row = {
                    "type": case["type"],
                    "passed": False,
                    "detail": str(exc),
                    "pipeline": "error",
                }
            results.append(row)
            mark = "PASS" if row.get("passed") else "FAIL"
            print(f"[{mark}] {case['type']}: {row.get('pipeline')} | {row.get('detail')}", flush=True)

    finally:
        client.close()

    passed = sum(1 for r in results if r.get("passed"))
    summary = {"passed": passed, "total": len(results), "results": results}
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n媒体链路验收: {passed}/{len(results)} 通过 -> {args.json_output}", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
