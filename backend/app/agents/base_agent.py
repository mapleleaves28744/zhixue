from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentContext, AgentResult


class BaseAgent(ABC):
    """Agent 抽象基类"""

    name: str
    description: str

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult: ...

    def success_result(
        self,
        data: dict[str, Any] | None = None,
        message: str = "",
        evidence: list[str] | None = None,
        next_actions: list[str] | None = None,
    ) -> AgentResult:
        return AgentResult(
            success=True,
            data=data or {},
            message=message,
            evidence=evidence or [],
            next_actions=next_actions or [],
        )

    def error_result(
        self,
        message: str = "",
        data: dict[str, Any] | None = None,
        evidence: list[str] | None = None,
    ) -> AgentResult:
        return AgentResult(
            success=False,
            data=data or {},
            message=message,
            evidence=evidence or [],
        )
