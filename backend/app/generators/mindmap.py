"""思维导图生成器。"""
from __future__ import annotations

from typing import Any

from app.generators.base import BaseGenerator, GeneratorResult
from app.llm import ChatMessage
from app.services.generator_registry import GeneratorRegistry


@GeneratorRegistry.register
class MindmapGenerator(BaseGenerator):
    resource_type = "mindmap"
    display_name = "思维导图"

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
        prompt = (
            f"请围绕知识点「{knowledge_name}」生成一份思维导图。\n\n"
            f"参考资料：\n{context[:2000]}\n\n"
            f"学生画像：{profile_text[:500]}\n\n"
            f"额外要求：{requirement or '无'}\n\n"
            "请用 Markdown 缩进列表格式输出思维导图结构，例如：\n"
            "## 中心主题\n"
            "- 分支 1\n"
            "  - 子节点 1.1\n"
            "  - 子节点 1.2\n"
            "- 分支 2\n"
            "  - 子节点 2.1\n"
        )

        if llm_provider is None:
            return GeneratorResult(
                content=f"# {knowledge_name} 思维导图\n\n（LLM 未连接，无法生成）",
                title=f"{knowledge_name}思维导图",
                resource_type=self.resource_type,
            )

        response = await llm_provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.6,
            max_tokens=2048,
        )

        return GeneratorResult(
            content=response.content,
            title=f"{knowledge_name}思维导图",
            resource_type=self.resource_type,
            metadata={"model": response.model},
        )
