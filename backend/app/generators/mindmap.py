"""思维导图（Mermaid mindmap）生成器。"""
from __future__ import annotations

from typing import Any

from app.generators.base import BaseGenerator, GeneratorResult
from app.llm import ChatMessage
from app.services.diagram_service import CONCISE_MERMAID_RULES
from app.services.generator_registry import GeneratorRegistry
from app.utils.mermaid_util import extract_mermaid_code


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
        depth = 4 if requirement and any(k in requirement for k in ("复杂", "多层", "详细")) else 3
        prompt = (
            f"请围绕知识点「{knowledge_name}」生成一个 Mermaid mindmap 思维导图。\n\n"
            f"参考资料：\n{context[:2000]}\n\n"
            f"学生画像：{profile_text[:500]}\n\n"
            f"额外要求：{requirement or '无'}\n\n"
            f"要求：\n"
            f"1. 使用 Mermaid mindmap 语法\n"
            f"2. 中心节点为「{knowledge_name}」，最大深度 {depth} 层\n"
            f"3. {CONCISE_MERMAID_RULES}\n"
            f"4. 只输出 Mermaid 代码，不要其他解释\n"
        )

        if llm_provider is None:
            fallback = (
                f"mindmap\n"
                f"  root(({knowledge_name[:40]}))\n"
                f"    核心概念\n"
                f"    典型操作\n"
                f"    应用场景"
            )
            return GeneratorResult(
                content=fallback,
                title=f"{knowledge_name}思维导图",
                resource_type=self.resource_type,
            )

        response = await llm_provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.5,
            max_tokens=2048,
        )
        mermaid_code = extract_mermaid_code(response.content, fallback_root=knowledge_name)

        return GeneratorResult(
            content=mermaid_code,
            title=f"{knowledge_name}思维导图",
            resource_type=self.resource_type,
            metadata={"model": response.model, "depth": depth},
        )
