from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.base_agent import BaseAgent


class AgentRegistry:
    """Agent 注册表，通过装饰器自动注册"""

    _registry: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_class: type[BaseAgent]) -> type[BaseAgent]:
        cls._registry[agent_class.name] = agent_class
        return agent_class

    @classmethod
    def get(cls, name: str) -> type[BaseAgent] | None:
        return cls._registry.get(name)

    @classmethod
    def all(cls) -> dict[str, type[BaseAgent]]:
        return dict(cls._registry)
