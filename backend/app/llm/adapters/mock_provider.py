from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import AsyncIterator

from app.llm.adapters.base import BaseLLMProvider
from app.llm.schemas import ChatMessage, ChatResponse, EmbeddingResponse, LLMModelConfig


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider for local development without API keys."""

    provider_name = "mock"
    embedding_dimension = 1024

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> ChatResponse:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        content = self._generate_response(last_user)
        return ChatResponse(
            content=content,
            model=model or (model_config.model if model_config else None) or "mock-learning-model",
            usage={
                "prompt_tokens": max(1, sum(len(m.content) for m in messages) // 4),
                "completion_tokens": max(1, len(content) // 4),
                "total_tokens": max(2, (sum(len(m.content) for m in messages) + len(content)) // 4),
            },
            raw={"provider": "mock"},
            provider=self.provider_name,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        response = await self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            model_config=model_config,
        )
        for paragraph in response.content.splitlines():
            if paragraph.strip():
                yield paragraph + "\n"

    async def embedding(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> EmbeddingResponse:
        embeddings = [_text_to_vec(text, self.embedding_dimension) for text in texts]
        token_count = sum(max(1, len(text) // 4) for text in texts)
        return EmbeddingResponse(
            embeddings=embeddings,
            model=model or (model_config.embedding_model if model_config else None) or "mock-embedding",
            usage={"prompt_tokens": token_count, "total_tokens": token_count},
            raw={"provider": "mock", "input_count": len(texts)},
            provider=self.provider_name,
        )

    def _generate_response(self, user_input: str) -> str:
        if not user_input:
            return "你好！我是智学工坊的 AI 学习助手，有什么可以帮助你的吗？"

        topic = self._detect_topic(user_input)

        if "个性化学习资源" in user_input or "资源类型" in user_input:
            return (
                f"# {topic}个性化讲解\n\n"
                "## 核心理解\n"
                f"{topic}需要先抓住定义、操作约束和复杂度三条主线。学习时不要只背概念，"
                "要把一次具体操作手工模拟出来，再对照代码实现。\n\n"
                "## 分步学习\n"
                "1. 写出该结构的逻辑关系和允许的基本操作。\n"
                "2. 用 3 到 5 个元素模拟插入、删除、查找或遍历。\n"
                "3. 对每一步标出时间复杂度，并说明空间开销来自哪里。\n\n"
                "## 小练习\n"
                f"请用自己的话解释{topic}在一个真实算法中的作用，并写出最容易出错的边界条件。\n\n"
                "## 个性化原因\n"
                "根据当前学习空间中的画像、记忆或补充要求，本资源采用分步骤说明和小练习收束，方便从概念过渡到题目应用。\n\n"
                "## 引用来源\n"
                "- 课程资料或 Wiki 检索片段；若本地尚未生成向量，以上为 Mock Provider 演示内容，建议核对资料。"
            )

        if "总结" in user_input or "摘要" in user_input:
            return (
                f"以下是「{topic}」的学习摘要：\n\n"
                f"1. 先把{topic}的定义、存储方式和基本操作区分清楚。\n"
                "2. 关注时间复杂度和空间复杂度，尤其是插入、删除、查找、遍历等操作。\n"
                "3. 用一个小规模样例手工模拟过程，再对照代码实现。\n\n"
                "来源说明：这是 Mock Provider 根据输入生成的演示内容，正式学习时应核对课程资料。"
            )

        if "wiki" in user_input.lower() or "生成" in user_input:
            return (
                f"# {topic}\n\n"
                "## 定义\n"
                f"{topic}是数据结构课程中的核心知识点，需要同时理解抽象逻辑结构、存储结构和典型操作。\n\n"
                "## 核心内容\n"
                "- 基本概念：明确元素之间的关系和约束。\n"
                "- 操作过程：掌握初始化、插入、删除、查找、遍历等常见操作。\n"
                "- 复杂度分析：比较不同实现方式在时间和空间上的代价。\n\n"
                "## 示例\n"
                f"可以用一组简单数据手工模拟{topic}的操作过程，再观察边界条件。\n\n"
                "## 学习建议\n"
                "建议结合课程资料、代码示例和练习题交替学习。若资料证据不足，请标记为 AI 推断内容并核对。"
            )

        if "笔记" in user_input:
            return (
                "根据你的笔记内容，我整理了以下要点：\n\n"
                "## 新增知识点\n"
                "- 补充了相关概念的详细解释\n"
                "- 添加了实际应用的案例说明\n\n"
                "## 与已有知识的关联\n"
                "该笔记内容与之前学习的章节有密切联系，建议综合复习。"
            )

        if "栈" in user_input or "队列" in user_input:
            return (
                "栈和队列都是受限线性表：栈遵循后进先出，常用于递归、表达式求值和括号匹配；"
                "队列遵循先进先出，常用于层序遍历、任务调度和缓冲区。学习时重点比较它们的操作端、"
                "典型应用和顺序/链式存储实现。\n\n"
                "来源说明：这是 Mock Provider 的数据结构演示回答，建议结合上传资料中的对应章节核对。"
            )

        if "树" in user_input or "二叉树" in user_input:
            return (
                "二叉树的关键是递归结构和遍历顺序。前序适合复制树结构，中序常用于二叉搜索树有序输出，"
                "后序适合释放或汇总子树信息，层序遍历通常借助队列实现。学习时要把递归定义、遍历代码和"
                "复杂度分析放在一起理解。"
            )

        if "图" in user_input:
            return (
                "图结构关注顶点、边、路径和连通性。邻接矩阵适合稠密图并能快速判断两点是否相邻，"
                "邻接表更适合稀疏图。BFS 常用于最短层数问题，DFS 常用于连通性、拓扑或回溯类问题。"
            )

        return (
            f"基于你的问题，以下是详细解答：\n\n"
            f"这个问题可以从「定义 → 操作 → 复杂度 → 应用场景」四个层次理解。"
            f"建议先定位对应 Wiki 页面或资料片段，再做一两道小题验证是否真正掌握。\n\n"
            f"来源说明：这是 Mock Provider 生成的本地演示回答，若没有引用资料，应标记为 AI 推断内容。"
        )

    def _detect_topic(self, user_input: str) -> str:
        for topic in ("栈与队列", "二叉树", "树", "图", "查找", "排序", "线性表", "串", "数组", "数据结构"):
            if topic in user_input:
                return topic
        return "知识点概述"


def _text_to_vec(text: str, dim: int) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    needed = dim * 4
    buf = (h * (needed // len(h) + 1))[:needed]
    floats = list(struct.unpack(f"{dim}f", buf))
    floats = [0.0 if not math.isfinite(f) else f for f in floats]
    norm = sum(f * f for f in floats) ** 0.5
    if norm > 0:
        floats = [f / norm for f in floats]
    return floats
