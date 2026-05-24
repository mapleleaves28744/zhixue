from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ChunkData:
    index: int
    content: str
    token_count: int


def chunk_text(
    text: str,
    max_tokens: int = 512,
    overlap: int = 50,
) -> list[ChunkData]:
    """Split parsed document text into retrievable chunks.

    Algorithm:
    1. Split on double-newline paragraph boundaries.
    2. Discard empty / whitespace-only paragraphs.
    3. Oversized paragraphs are sub-split by character limit.
    4. Adjacent chunks share ``overlap`` characters for context continuity.
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        return []

    raw_segments: list[str] = []
    for para in paragraphs:
        if len(para) <= max_tokens:
            raw_segments.append(para)
        else:
            raw_segments.extend(_split_long_paragraph(para, max_tokens))

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
            )
        )

    return chunks


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
