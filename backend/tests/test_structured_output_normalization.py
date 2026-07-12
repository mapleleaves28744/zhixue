from __future__ import annotations

import unittest

from app.agents.structured_outputs import EvolutionAnalysisOutput, MemoryReflectOutput, ReviewOutput


class StructuredOutputNormalizationTests(unittest.TestCase):
    def test_memory_evidence_string_is_normalized_to_list(self) -> None:
        output = MemoryReflectOutput.model_validate(
            {"memories": [{"content": "循环队列薄弱", "evidence": "quiz_id=abc"}]}
        )
        self.assertEqual(output.memories[0].evidence, ["quiz_id=abc"])

    def test_flat_evolution_output_is_wrapped_as_one_strategy(self) -> None:
        output = EvolutionAnalysisOutput.model_validate(
            {
                "change_summary": "增加循环队列练习",
                "before_snapshot": {"difficulty": "medium"},
                "after_snapshot": {"difficulty": "easy"},
                "risk_level": "low",
                "evidence": "quiz wrong",
            }
        )
        self.assertEqual(len(output.strategies), 1)
        self.assertEqual(output.strategies[0].change_summary, "增加循环队列练习")

    def test_review_issue_objects_are_normalized_to_descriptions(self) -> None:
        output = ReviewOutput.model_validate(
            {
                "pass": False,
                "issues": [{"type": "知识偏离", "description": "缺少可靠来源", "severity": "high"}],
            }
        )
        self.assertEqual(output.issues, ["知识偏离：缺少可靠来源"])
