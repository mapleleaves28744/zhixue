from uuid import uuid4

from app.rag.evidence import EvidenceItem
from app.services.citation_validator import CitationValidator


def _document(key: str) -> EvidenceItem:
    return EvidenceItem(
        citation_key=key,
        source_type="document",
        source_id=uuid4(),
        chunk_id=uuid4(),
        title="数据结构讲义",
        quote="栈遵循后进先出原则。",
        retrieval_mode="hybrid",
        confidence="strong",
    )


def test_validator_keeps_only_used_known_citations_in_answer_order() -> None:
    s1, s2 = _document("S1"), _document("S2")
    result = CitationValidator().validate("结论一 [S2]，结论二 [S9]，再次引用 [S2]。", [s1, s2])

    assert [item.citation_key for item in result.citations] == ["S2"]
    assert result.unknown_keys == ["S9"]
    assert result.grounding_status == "grounded"


def test_validator_marks_supported_answer_without_marker_as_partial() -> None:
    result = CitationValidator().validate("栈遵循后进先出原则。", [_document("S1")])

    assert result.citations == []
    assert result.grounding_status == "partial"


def test_validator_marks_no_evidence_as_insufficient() -> None:
    result = CitationValidator().validate("课程资料中没有可验证依据。", [])

    assert result.citations == []
    assert result.grounding_status == "insufficient"
