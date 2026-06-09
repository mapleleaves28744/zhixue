"""Normalize agent final answers — unwrap JSON envelopes from Supervisor LLM output."""

from __future__ import annotations

import json
import re
from typing import Any


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    return re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE).strip().removesuffix("```").strip()


def extract_final_answer_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    candidates = [text, _strip_code_fence(text)]
    for candidate in candidates:
        if not candidate.startswith("{"):
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        inner = data.get("final_answer") or data.get("answer")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
        if data.get("status") == "complete" and isinstance(data.get("summary"), str):
            # JSON decision without a separate final_answer — avoid showing raw JSON
            summary = str(data["summary"]).strip()
            if summary and not summary.startswith("{"):
                return summary

    return text
