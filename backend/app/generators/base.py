"""生成器插件基类。

所有资源生成器继承 BaseGenerator 并通过 @GeneratorRegistry.register 注册。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GeneratorResult:
    """生成器输出载体。"""
    content: str
    title: str = ""
    resource_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str = ""


class BaseGenerator(ABC):
    """资源生成器基类。

    子类必须定义:
      - resource_type: 对应的资源类型标识
      - display_name: 中文显示名
      - generate(): 核心生成逻辑
    """
    resource_type: str = ""
    display_name: str = ""

    @abstractmethod
    async def generate(
        self,
        *,
        knowledge_name: str,
        context: str,
        profile_text: str = "",
        requirement: str = "",
        llm_provider: Any = None,
        **kwargs: Any,
    ) -> GeneratorResult:
        """生成资源内容。

        Args:
            knowledge_name: 知识点名称
            context: RAG 检索到的参考上下文
            profile_text: 学生画像文本
            requirement: 用户额外要求
            llm_provider: LLM provider 实例
            **kwargs: 扩展参数

        Returns:
            GeneratorResult 包含生成的内容
        """
        ...

    def _build_prompt(
        self,
        *,
        knowledge_name: str,
        context: str,
        profile_text: str,
        requirement: str,
    ) -> str:
        """构建默认 prompt，子类可覆盖。"""
        return (
            f"请围绕知识点「{knowledge_name}」生成一份{self.display_name}。\n\n"
            f"参考资料：\n{context[:2000]}\n\n"
            f"学生画像：{profile_text[:500]}\n\n"
            f"额外要求：{requirement or '无'}\n\n"
            f"请用 Markdown 格式输出。"
        )
