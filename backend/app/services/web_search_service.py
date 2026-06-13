"""AnySearch 联网搜索服务。"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import settings

_ANYSEARCH_ENDPOINT = "https://api.anysearch.com/mcp"
_RESULT_BLOCK_PATTERN = re.compile(
    r"###\s+\d+\.\s+(.+?)\n-\s+\*\*URL\*\*:\s+(\S+)\n(?:-\s+(.+?))?(?=\n###|\n##|\Z)",
    re.DOTALL,
)


class WebSearchService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.anysearch_api_key).strip()
        self.endpoint = (endpoint or settings.anysearch_base_url or _ANYSEARCH_ENDPOINT).strip()
        self.timeout_seconds = timeout_seconds
        self.enabled = settings.anysearch_enabled and bool(self.api_key)

    async def search(
        self,
        *,
        query: str,
        max_results: int = 5,
        domain: str | None = None,
    ) -> dict[str, Any]:
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            return {"query": "", "items": [], "citations": [], "provider": "anysearch", "message": "搜索词不能为空"}

        if not self.enabled:
            return self._mock_response(cleaned_query, max_results)

        raw_text = await self._call_api(
            tool_name="search",
            arguments=self._build_search_arguments(cleaned_query, max_results, domain),
        )
        items = self._parse_markdown_results(raw_text)
        citations = [
            {
                "source_type": "web",
                "title": item["title"],
                "url": item["url"],
                "quote": item.get("snippet") or "",
            }
            for item in items
        ]
        return {
            "query": cleaned_query,
            "items": items,
            "citations": citations,
            "provider": "anysearch",
            "raw_text": raw_text,
        }

    async def extract_page(self, *, url: str) -> dict[str, Any]:
        cleaned_url = str(url or "").strip()
        if not cleaned_url:
            return {"url": "", "content": "", "provider": "anysearch", "message": "URL 不能为空"}
        if not self.enabled:
            return {
                "url": cleaned_url,
                "content": f"[Mock] 无法在无 API Key 时抓取网页：{cleaned_url}",
                "provider": "mock",
            }
        content = await self._call_api(tool_name="extract", arguments={"url": cleaned_url})
        return {"url": cleaned_url, "content": content, "provider": "anysearch"}

    async def _call_api(self, *, tool_name: str, arguments: dict[str, Any]) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            message = data["error"].get("message", str(data["error"]))
            raise RuntimeError(f"AnySearch API 错误: {message}")

        result = data.get("result", {})
        content = result.get("content", [])
        for item in content:
            if item.get("type") == "text":
                return str(item.get("text") or "")
        return json.dumps(result, ensure_ascii=False)

    def _build_search_arguments(
        self,
        query: str,
        max_results: int,
        domain: str | None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {"query": query, "max_results": min(max(max_results, 1), 10)}
        if domain:
            arguments["domain"] = domain
        return arguments

    def _parse_markdown_results(self, raw_text: str) -> list[dict[str, str]]:
        text = str(raw_text or "").strip()
        if not text:
            return []
        items: list[dict[str, str]] = []
        for match in _RESULT_BLOCK_PATTERN.finditer(text):
            title = match.group(1).strip()
            url = match.group(2).strip()
            snippet = (match.group(3) or "").strip()
            items.append({"title": title, "url": url, "snippet": snippet})
        if items:
            return items
        return [{"title": "联网搜索结果", "url": "", "snippet": text[:800]}]

    def _mock_response(self, query: str, max_results: int) -> dict[str, Any]:
        items = [
            {
                "title": f"关于「{query}」的演示搜索结果",
                "url": "https://example.com/mock-search",
                "snippet": "当前未配置 ANYSEARCH_API_KEY，返回 Mock 联网搜索结果。配置后可调用 AnySearch 实时搜索。",
            }
        ][: max(max_results, 1)]
        citations = [
            {
                "source_type": "web",
                "title": item["title"],
                "url": item["url"],
                "quote": item["snippet"],
            }
            for item in items
        ]
        return {
            "query": query,
            "items": items,
            "citations": citations,
            "provider": "mock",
            "message": "未配置 ANYSEARCH_API_KEY，已使用 Mock 联网搜索。",
        }
