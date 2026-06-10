"""图解（Mermaid 流程图）生成器。"""
from __future__ import annotations

import re
from typing import Any

from app.generators.base import BaseGenerator, GeneratorResult
from app.llm import ChatMessage
from app.services.diagram_service import CONCISE_MERMAID_RULES
from app.services.generator_registry import GeneratorRegistry
from app.utils.mermaid_util import extract_mermaid_code


@GeneratorRegistry.register
class DiagramGenerator(BaseGenerator):
    resource_type = "diagram"
    display_name = "图解"

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
            f"请围绕知识点「{knowledge_name}」生成一个 Mermaid flowchart TD 流程图。\n\n"
            f"参考资料：\n{context[:2000]}\n\n"
            f"学生画像：{profile_text[:500]}\n\n"
            f"额外要求：{requirement or '无'}\n\n"
            f"要求：只输出 Mermaid 代码；{CONCISE_MERMAID_RULES}\n"
            "无法从资料确认的内容标注为 AI 推断。"
        )

        if llm_provider is None:
            fallback = (
                f"flowchart TD\n"
                f"  A[{knowledge_name}]\n"
                f"  B[核心概念]\n"
                f"  C[典型应用]\n"
                f"  A --> B --> C"
            )
            return GeneratorResult(
                content=fallback,
                title=f"{knowledge_name}图解",
                resource_type=self.resource_type,
            )

        response = await llm_provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.5,
            max_tokens=2048,
        )
        mermaid_code = extract_mermaid_code(response.content, fallback_root=knowledge_name)
        if not mermaid_code.startswith("flowchart"):
            mermaid_code = re.sub(
                r"^mindmap.*",
                f"flowchart TD\n  root[{knowledge_name}]",
                mermaid_code,
                count=1,
                flags=re.DOTALL,
            )

        return GeneratorResult(
            content=mermaid_code,
            title=f"{knowledge_name}图解",
            resource_type=self.resource_type,
            metadata={"model": response.model},
        )
