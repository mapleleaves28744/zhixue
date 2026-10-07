"""Narrow, source-traced session instructions derived from explicit user text."""

from __future__ import annotations

import re
from typing import Any


_SESSION_START = re.compile(
    r"^\s*(?:请|麻烦)?\s*(?:后面|接下来|以后|之后|从现在开始|后续|本次对话|这段对话)"
)
_NEGATE_ENGLISH = re.compile(r"(?:不用|不要|别用|不再用|别再用)英文|不再英文回答")
_ENGLISH = re.compile(r"用英文|英文回答|英语回答")
_CHINESE = re.compile(r"用中文|中文回答|汉语回答")
_CONCISE = re.compile(r"简短|简洁|精简|简单一点|短一点")
_DETAILED = re.compile(r"详细|展开讲|讲细|深入一点")
_NO_EXAMPLES = re.compile(r"不(?:要|用|再)?举例|不要例子|不用例子")
_EXAMPLES_FIRST = re.compile(r"先(?:给|举|看)(?:个|一个|些)?例子|先举例")
_NO_CONCLUSION_FIRST = re.compile(r"(?:不要|不用|别|不再)(?:再)?(?:先给|先说)结论|不必先给结论")
_CONCLUSION_FIRST = re.compile(r"先(?:给|说)结论|结论优先")

_DISPLAY = {
    ("language", "en"): "后续回答使用英文",
    ("language", "zh"): "后续回答使用中文",
    ("detail", "concise"): "后续回答尽量简短",
    ("detail", "detailed"): "后续回答适当展开",
    ("examples", "none"): "后续回答不主动举例",
    ("examples", "first"): "后续回答先给例子",
    ("opening", "conclusion_first"): "后续回答先给结论，再展开说明",
    ("format", "bullets"): "后续回答使用分点列举",
    ("format", "paragraphs"): "后续回答使用自然段",
}


def parse_session_changes(text: str) -> dict[str, str | None]:
    value = text.strip()
    # A separate following question does not cancel an explicit session instruction.
    clauses = re.split(r"[。；;\n]", value)
    value = clauses[0]
    if not _SESSION_START.match(value) or "?" in value or "？" in value:
        return {}
    # Only explicitly scoped subsequent sentences may add persistent instructions.
    # Quoted course text and following ordinary questions never become constraints.
    if len(clauses) > 1:
        changes = parse_session_changes(value)
        for clause in clauses[1:]:
            if _SESSION_START.match(clause):
                changes.update(parse_session_changes(clause))
        return changes
    changes: dict[str, str | None] = {}
    if re.search(r"(?:恢复|取消|清除|重置)(?:之前|原来|所有|全部|本次)?(?:的)?(?:回答|会话|表达)?(?:要求|约束|风格)", value):
        return {key: None for key in ("language", "detail", "examples", "opening", "format")}
    if _CHINESE.search(value):
        changes["language"] = "zh"
    elif _NEGATE_ENGLISH.search(value):
        changes["language"] = None
    elif _ENGLISH.search(value):
        changes["language"] = "en"
    if re.search(r"(?:不要|不用|别|不再)(?:再)?(?:简短|简洁|精简)", value):
        changes["detail"] = "detailed" if _DETAILED.search(value) else None
    elif re.search(r"(?:不要|不用|别|不再)(?:再)?(?:详细|展开讲|讲细)", value):
        changes["detail"] = "concise" if _CONCISE.search(value) else None
    elif _CONCISE.search(value):
        changes["detail"] = "concise"
    elif _DETAILED.search(value):
        changes["detail"] = "detailed"
    if _NO_EXAMPLES.search(value):
        changes["examples"] = "none"
    elif _EXAMPLES_FIRST.search(value):
        changes["examples"] = "first"
    if _NO_CONCLUSION_FIRST.search(value):
        changes["opening"] = None
    elif _CONCLUSION_FIRST.search(value):
        changes["opening"] = "conclusion_first"
    if re.search(r"(?:不要|不用|别)(?:再)?(?:分点|列点|列举)", value):
        changes["format"] = "paragraphs"
    elif re.search(r"分点|列点|用列表|条目形式", value):
        changes["format"] = "bullets"
    elif re.search(r"自然段|段落形式", value):
        changes["format"] = "paragraphs"
    return changes


def apply_session_changes(
    active: dict[str, dict[str, Any]], *, text: str, source: Any,
) -> dict[str, dict[str, Any]]:
    updated = dict(active)
    for key, value in parse_session_changes(text).items():
        if value is None:
            updated.pop(key, None)
        else:
            updated[key] = {
                "value": value,
                "source_message_id": str(getattr(source, "id", "") or ""),
                "source_sequence": int(getattr(source, "sequence_no", 0) or 0),
            }
    return updated


def render_session_constraints(active: dict[str, dict[str, Any]]) -> str:
    lines = []
    for key in ("language", "detail", "examples", "opening", "format"):
        item = active.get(key) or {}
        phrase = _DISPLAY.get((key, str(item.get("value") or "")))
        if phrase:
            lines.append(phrase)
    return "；".join(lines)
