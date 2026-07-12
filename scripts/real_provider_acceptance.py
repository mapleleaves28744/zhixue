from __future__ import annotations

import re
from typing import Any


REAL_PROVIDER_DENYLIST = {"", "mock", "fallback", "mock_multimodal", "mock_audio"}


def classify_provider(payload: dict[str, Any]) -> str:
    provider = str(payload.get("provider") or "").strip().lower()
    if payload.get("fallback_used") or provider == "fallback":
        return "fallback"
    return "real" if provider not in REAL_PROVIDER_DENYLIST else "mock"


def require_real_response(payload: dict[str, Any], scenario: str) -> None:
    state = classify_provider(payload)
    if state != "real":
        raise RuntimeError(
            f"{scenario}: expected real provider, got {state} ({payload.get('provider')!r})"
        )


def sanitize_error(value: str) -> str:
    return re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]", value)
