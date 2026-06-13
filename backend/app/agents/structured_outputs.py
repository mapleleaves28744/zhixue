"""Pydantic schemas for Agent structured_chat() outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuizQuestionLLM(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_type: str | None = None
    difficulty: str | None = None
    question_text: str | None = None
    stem: str | None = None
    options: list[Any] | dict[str, Any] | None = None
    standard_answer: str | None = None
    correct_answer: str | None = None
    analysis: str | None = None
    explanation: str | None = None
    error_tags: list[str] | None = None


class QuizGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    questions: list[QuizQuestionLLM] = Field(default_factory=list)


class ReviewOutput(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    passed: bool = Field(default=True, alias="pass")
    risk_level: Literal["low", "medium", "high"] = "medium"
    issues: list[str] = Field(default_factory=list)
    revision_suggestions: str | list[str] = ""

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk(cls, value: object) -> str:
        text = str(value or "medium").lower()
        if text in {"low", "medium", "high"}:
            return text
        return "medium"

    def to_dict(self) -> dict[str, Any]:
        suggestions = self.revision_suggestions
        if isinstance(suggestions, list):
            suggestions = "\n".join(str(item) for item in suggestions if str(item).strip())
        return {
            "pass": self.passed,
            "risk_level": self.risk_level,
            "issues": list(self.issues),
            "revision_suggestions": str(suggestions or ""),
        }


class EvolutionStrategyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strategy_type: str = "recommendation"
    before_value: dict[str, Any] = Field(default_factory=dict)
    after_value: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    change_summary: str = ""
    risk_level: str = "medium"
    evidence: list[Any] | dict[str, Any] | str | None = None


class EvolutionAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strategies: list[EvolutionStrategyItem] = Field(min_length=1)


class MemoryItemOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    memory_type: str = "insight"
    content: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.8


class MemoryReflectOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    memories: list[MemoryItemOutput] = Field(default_factory=list)


class ProfileRebuildOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile_summary: str = ""
    mastery_snapshot: dict[str, Any] = Field(default_factory=dict)
    weak_points: list[str] = Field(default_factory=list)
    error_patterns: list[str] = Field(default_factory=list)
    strategy_summary: dict[str, Any] = Field(default_factory=dict)
