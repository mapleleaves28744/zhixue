from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class AgentContext:
    """Agent 输入上下文"""

    user_id: UUID
    course_id: UUID
    task_type: str  # e.g. "document_to_wiki", "course_qa"
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    run_id: UUID | None = None  # 当前 agent_runs 记录 ID


@dataclass
class AgentResult:
    """Agent 统一返回"""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    evidence: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
