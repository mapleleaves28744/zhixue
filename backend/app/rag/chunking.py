from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class ChunkData:
    index: int
    content: str
    token_count: int
    extra_meta: dict[str, Any] = field(default_factory=dict)


def chunk_text(
    text: str,
    max_tokens: int = 512,
    overlap: int = 50,
    source_metadata: dict[str, Any] | None = None,
) -> list[ChunkData]:
    """Split parsed document text into retrievable chunks.

    Algorithm:
    1. Track Markdown heading hierarchy as retrieval metadata.
    2. Split on paragraph / code-block boundaries while preserving code blocks.
    3. Oversized non-code paragraphs are sub-split by character limit.
    4. Adjacent chunks share ``overlap`` characters for context continuity.
    """
    source_metadata = dict(source_metadata or {})
    segments = _markdown_segments(text)
    if not segments:
        return []

    raw_segments: list[str] = []
    raw_meta: list[dict[str, Any]] = []
    for segment in segments:
        content = segment["content"].strip()
        if not content:
            continue
        meta = {
            **source_metadata,
            "heading_path": segment["heading_path"],
            "segment_type": segment["segment_type"],
            "chunk_type": _classify_chunk_type(content, segment["segment_type"]),
        }
        if len(content) <= max_tokens or segment["segment_type"] == "code":
            raw_segments.append(content)
            raw_meta.append(meta)
        else:
            for part in _split_long_paragraph(content, max_tokens):
                raw_segments.append(part)
                raw_meta.append(meta)

    chunks: list[ChunkData] = []
    for i, segment in enumerate(raw_segments):
        content = segment
        if overlap > 0 and i > 0 and len(raw_segments[i - 1]) >= overlap:
            prefix = raw_segments[i - 1][-overlap:]
            content = prefix + content
        chunks.append(
            ChunkData(
                index=i,
                content=content,
                token_count=len(content),
                extra_meta=raw_meta[i],
            )
        )

    return chunks


def _markdown_segments(text: str) -> list[dict[str, Any]]:
    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_heading: list[str] = []
    current_type = "text"
    in_code_block = False
    segments: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current_lines, current_type, current_heading
        content = "\n".join(current_lines).strip()
        if content:
            segments.append(
                {
                    "content": content,
                    "heading_path": list(current_heading),
                    "segment_type": current_type,
                }
            )
        current_lines = []
        current_type = "text"
        current_heading = list(heading_stack)

    for line in text.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading_match and not in_code_block:
            flush()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            current_heading = list(heading_stack)
            current_lines = [line]
            current_type = "heading"
            continue

        if line.strip().startswith("```"):
            if not in_code_block:
                flush()
                current_heading = list(heading_stack)
                current_type = "code"
                current_lines = [line]
                in_code_block = True
            else:
                current_lines.append(line)
                in_code_block = False
                flush()
            continue

        if not in_code_block and not line.strip():
            flush()
            continue

        if not current_lines:
            current_heading = list(heading_stack)
            current_type = "code" if in_code_block else "text"
        current_lines.append(line)

    flush()
    return segments


def _split_long_paragraph(text: str, max_tokens: int) -> list[str]:
    """Split a long paragraph by sentences / punctuation, respecting max_tokens."""
    sentences = re.split(r"(?<=[。！？.!?\n])", text)
    sentences = [s for s in sentences if s]

    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= max_tokens:
            current += sentence
        else:
            if current:
                parts.append(current)
            # If a single sentence exceeds max_tokens, hard-split
            while len(sentence) > max_tokens:
                parts.append(sentence[:max_tokens])
                sentence = sentence[max_tokens:]
            current = sentence
    if current:
        parts.append(current)

    return parts


def _classify_chunk_type(content: str, segment_type: str) -> str:
    if segment_type == "code" or content.strip().startswith("```"):
        return "code"
    lowered = content.lower()
    if "|" in content and re.search(r"\|[-:\s|]+\|", content):
        return "table"
    if any(marker in content for marker in ("复杂度", "时间复杂度", "空间复杂度", "O(")):
        return "complexity"
    if any(marker in content for marker in ("易错", "常见错误", "误区", "混淆")):
        return "misconception"
    if any(marker in content for marker in ("例如", "示例", "例子", "example")):
        return "example"
    if any(marker in content for marker in ("练习", "题目", "exercise", "problem")):
        return "exercise"
    if (
        " is " in lowered
        or " are " in lowered
        or "定义" in content
        or "是" in content[:80]
        or "指" in content[:80]
    ):
        return "definition"
    return "concept"
