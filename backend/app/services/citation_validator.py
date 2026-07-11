from __future__ import annotations

import re

from app.rag.evidence import CitationValidationResult, EvidenceItem


class CitationValidator:
    _marker = re.compile(r"\[(S\d+)\]")

    def validate(self, answer: str, evidence: list[EvidenceItem]) -> CitationValidationResult:
        by_key = {item.citation_key: item for item in evidence}
        seen: set[str] = set()
        used: list[EvidenceItem] = []
        unknown: list[str] = []
        for key in self._marker.findall(answer):
            if key in seen:
                continue
            seen.add(key)
            item = by_key.get(key)
            if item is None:
                unknown.append(key)
            else:
                used.append(item)
        if not evidence:
            status = "insufficient"
            message = "课程资料未找到可靠依据。"
        elif used:
            status = "grounded"
            message = f"回答已绑定 {len(used)} 条课程依据。"
        else:
            status = "partial"
            message = "已检索到课程依据，但回答未完整绑定来源。"
        return CitationValidationResult(used, unknown, status, message)
