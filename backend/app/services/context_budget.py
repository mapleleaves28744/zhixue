"""Conservative token budgeting when a provider tokenizer is unavailable."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=4)
def _tokenizer(path: str):
    if not path:
        return None
    try:
        from tokenizers import Tokenizer
        return Tokenizer.from_file(path)
    except Exception:
        logging.getLogger(__name__).warning("Configured tokenizer unavailable; using conservative context estimate")
        return None


def estimate_tokens(value: str) -> int:
    """Use the configured tokenizer, otherwise a UTF-8 byte upper bound.

    Average characters-per-token heuristics undercount random ASCII, emoji and
    code. A byte bound is intentionally less efficient but safer for BPE text.
    Provider-reported usage remains the source for cost/quality evaluation.
    """
    tokenizer = _tokenizer(str(getattr(settings, "llm_tokenizer_path", "") or ""))
    if tokenizer is not None:
        return len(tokenizer.encode(value, add_special_tokens=False).ids) + 8
    return len(value.encode("utf-8")) + 8


def truncate_to_tokens(value: str, limit: int) -> str:
    if limit <= 8:
        return ""
    if estimate_tokens(value) <= limit:
        return value
    low, high = 0, len(value)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(value[:middle]) <= limit - 1:
            low = middle
        else:
            high = middle - 1
    return value[:low] + "…" if low else ""


def input_token_limit(*, output_reserve: int, schema_reserve: int = 0) -> int:
    """Cap input by the configured model window and a safety margin."""
    return max(
        1024,
        min(24000, settings.llm_context_window_tokens - output_reserve - schema_reserve - 1024),
    )
