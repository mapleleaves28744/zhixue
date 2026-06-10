"""播客脚本生成器。"""
from __future__ import annotations

from typing import Any

from app.generators.base import BaseGenerator, GeneratorResult
from app.llm import ChatMessage
from app.services.generator_registry import GeneratorRegistry


@GeneratorRegistry.register
class PodcastScriptGenerator(BaseGenerator):
    resource_type = "podcast_script"
    display_name = "播客脚本"

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
            f"请围绕知识点「{knowledge_name}」生成一段播客对话脚本（两位主持人：老师 A 和学生 B）。\n\n"
            f"参考资料：\n{context[:2000]}\n\n"
            f"学生画像：{profile_text[:500]}\n\n"
            f"额外要求：{requirement or '无'}\n\n"
            "要求：\n"
            "- 对话自然、口语化\n"
            "- 老师循循善诱，学生提出常见疑问\n"
            "- 时长约 3-5 分钟\n"
            "- 用 Markdown 格式，每行以 **A:** 或 **B:** 开头\n"
        )

        if llm_provider is None:
            return GeneratorResult(
                content=(
                    f"# {knowledge_name} 播客脚本\n\n"
                    "**A:** 同学们好，今天我们来聊聊这个知识点。\n"
                    "**B:** 老师好！（LLM 未连接，无法生成完整脚本）"
                ),
                title=f"{knowledge_name}播客脚本",
                resource_type=self.resource_type,
            )

        response = await llm_provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.8,
            max_tokens=3000,
        )

        return GeneratorResult(
            content=response.content,
            title=f"{knowledge_name}播客脚本",
            resource_type=self.resource_type,
            metadata={"model": response.model, "format": "podcast_dialogue"},
        )
