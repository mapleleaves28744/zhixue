"""Bounded full-material summaries; every accepted source byte enters a map call."""
from __future__ import annotations

from typing import Any

from app.llm.schemas import ChatMessage
from app.services.prompt_service import PromptService


def source_batches(chunks: list[Any], *, byte_limit: int = 16000, max_batches: int = 24) -> list[str]:
    if byte_limit < 128 or max_batches < 1:
        raise ValueError("Invalid source batch limits")
    batches: list[str] = []
    current = ""
    for chunk in chunks:
        text = str(chunk.content or "")
        position = 0
        while position < len(text):
            prefix = f"\n[片段 {chunk.id}，页码 {getattr(chunk, 'page_no', None)}]\n"
            if len(prefix.encode("utf-8")) >= byte_limit:
                raise ValueError("Source identity exceeds batch capacity")
            room = byte_limit - len((current + prefix).encode("utf-8"))
            if room < 4:
                if current:
                    batches.append(current)
                current = ""
                continue
            low, high = 0, len(text) - position
            while low < high:
                middle = (low + high + 1) // 2
                if len(text[position:position + middle].encode("utf-8")) <= room:
                    low = middle
                else:
                    high = middle - 1
            if not low:
                raise ValueError("Cannot fit source text")
            current += prefix + text[position:position + low]
            position += low
            if position < len(text):
                batches.append(current)
                current = ""
            if len(batches) >= max_batches and (current or position < len(text)):
                raise ValueError("Material exceeds synchronous summary budget; split by chapter")
    if current:
        batches.append(current)
    if len(batches) > max_batches:
        raise ValueError("Material exceeds synchronous summary budget; split by chapter")
    return batches


class MaterialSummaryService:
    def __init__(self, db: Any) -> None:
        self.prompts = PromptService(db)

    async def summarize(self, *, chunks: list[Any], title: str, question: str, provider: Any) -> str:
        batches = source_batches(chunks)
        if not batches:
            raise ValueError("Material has no readable content")
        # Validate all bounds before making any expensive model calls.
        summaries = []
        for index, text in enumerate(batches):
            rendered = await self.prompts.render_prompt(agent_name="TutorAgent", scene="tutor.material_summary_map",
                params={"title": title, "question": question, "part": f"{index + 1}/{len(batches)}", "content": text})
            response = await provider.chat([ChatMessage(role="user", content=rendered.content)],
                temperature=0, max_tokens=600, thinking={"type": "disabled"}, prompt_version_id=rendered.prompt_version_id)
            if (response.raw or {}).get("fallback_used") or not response.content.strip():
                raise ValueError("A source batch could not be summarized reliably")
            summaries.append(f"批次 {index + 1}：{response.content}")
        # Hierarchical reduction keeps every map result without prefix truncation.
        while len(summaries) > 1:
            reduced = []
            for offset in range(0, len(summaries), 4):
                rendered = await self.prompts.render_prompt(agent_name="TutorAgent", scene="tutor.material_summary_reduce",
                    params={"title": title, "question": question, "content": "\n\n".join(summaries[offset:offset + 4])})
                response = await provider.chat([ChatMessage(role="user", content=rendered.content)], temperature=0,
                    max_tokens=1000, thinking={"type": "disabled"}, prompt_version_id=rendered.prompt_version_id)
                if (response.raw or {}).get("fallback_used") or not response.content.strip():
                    raise ValueError("Summary reduction failed")
                reduced.append(response.content)
            summaries = reduced
        return f"已读取整份已解析资料的 {len(chunks)} 个切片（{len(batches)} 个正文批次）；摘要仍可能遗漏细节，请结合原文核对。\n\n{summaries[0]}"
