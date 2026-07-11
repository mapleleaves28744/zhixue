from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from collections.abc import AsyncIterator

from app.llm.adapters.base import BaseLLMProvider
from app.llm.schemas import ChatMessage, ChatResponse, EmbeddingResponse, LLMModelConfig, ToolCall


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
        tools = kwargs.get("tools")
        if isinstance(tools, list) and tools:
            planned = self._supervisor_tool_call(messages, tools)
            if planned is not None:
                return planned
        response_format = kwargs.get("response_format")
        schema_name = None
        if isinstance(response_format, dict):
            json_schema = response_format.get("json_schema")
            if isinstance(json_schema, dict):
                schema_name = json_schema.get("name")
        if schema_name:
            content = self._generate_structured_response(schema_name, last_user)
        else:
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

    def _generate_structured_response(self, schema_name: str, user_input: str) -> str:
        topic = self._detect_topic(user_input)
        if schema_name == "QuizGenerationOutput":
            return self._generate_quiz_response(user_input, topic)
        if schema_name == "ReviewOutput":
            return json.dumps(
                {
                    "pass": True,
                    "risk_level": "low",
                    "issues": [],
                    "revision_suggestions": "内容结构清晰，建议继续补充课程引用。",
                },
                ensure_ascii=False,
            )
        if schema_name == "EvolutionAnalysisOutput":
            return json.dumps(
                {
                    "strategies": [
                        {
                            "strategy_type": "recommendation",
                            "before_value": {"focus": topic},
                            "after_value": {"focus": f"{topic}薄弱点强化"},
                            "description": f"基于近期学习证据，建议优先复习{topic}相关练习。",
                            "risk_level": "low",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        if schema_name == "MemoryReflectOutput":
            return json.dumps(
                {
                    "memories": [
                        {
                            "memory_type": "insight",
                            "content": f"学生近期围绕{topic}进行了多次学习活动，建议保持练习频率。",
                            "evidence": ["mock-learning-records"],
                            "confidence": 0.82,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        if schema_name == "ProfileRebuildOutput":
            return json.dumps(
                {
                    "profile_summary": f"基于学习记录，该学生在{topic}上需要继续巩固。",
                    "mastery_snapshot": {topic: 0.62},
                    "weak_points": [topic],
                    "error_patterns": ["边界条件遗漏"],
                    "strategy_summary": {"建议": "先复习定义，再做小练习验证。"},
                },
                ensure_ascii=False,
            )
        return self._generate_response(user_input)

    def _generate_response(self, user_input: str) -> str:
        if not user_input:
            return "你好！我是智学工坊的 AI 学习助手，有什么可以帮助你的吗？"

        grounded_tutor = self._generate_grounded_tutor_response(user_input)
        if grounded_tutor is not None:
            return grounded_tutor

        topic = self._detect_topic(user_input)

        if self._is_provider_status_question(user_input):
            return (
                "当前这条回答来自 Mock Provider。系统已经优先尝试调用真实大模型；"
                "如果页面仍显示 mock，通常说明真实 Provider 调用失败后触发了演示兜底。\n\n"
                "最常见原因包括：API Key 无效或过期、Base URL 不匹配、模型名没有权限、接口返回 401/403，"
                "或本地网络无法访问模型服务。\n\n"
                "你可以查看回答下方的 Provider / failed_provider / fallback 信息来判断："
                "若 failed_provider 是 xiaomi_mimo，说明小米 MiMo 已经被请求过，但失败后回退到了 Mock。"
            )

        if (
            '"slides"' in user_input
            and "module_label" in user_input
            and ("course-module" in user_input or "objectives" in user_input)
        ):
            return self._generate_html_ppt_outline(user_input, topic)

        if "Quiz Agent" in user_input or "结构化练习题" in user_input or "error_tags" in user_input:
            return self._generate_quiz_response(user_input, topic)

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

    def _generate_html_ppt_outline(self, user_input: str, topic: str) -> str:
        return json.dumps(
            {
                "title": f"{topic} 互动课件",
                "module_label": f"智学工坊 · {topic}",
                "duration_hint": "~15 min",
                "prereq": "课程前置章节",
                "objectives": [
                    f"理解 {topic} 的定义",
                    f"掌握 {topic} 的核心性质",
                    f"能举例说明 {topic} 的应用",
                    "完成自测并核对理解",
                ],
                "slides": [
                    {
                        "type": "cover",
                        "kicker": "智学工坊 · 互动课件",
                        "title": topic,
                        "subtitle": f"围绕「{topic}」的分步互动学习模块。",
                        "pills": ["~15 min", "html-ppt-skill", "course-module"],
                    },
                    {
                        "type": "objectives",
                        "title": "本模块结束后，你将能够…",
                        "boxes": [
                            {"title": f"① 解释 {topic}", "body": "用自己的话说明定义与术语。"},
                            {"title": f"② 分析 {topic} 性质", "body": "联系课程资料中的关键结论。"},
                            {"title": "③ 完成自测", "body": "通过选择题检验理解。"},
                        ],
                    },
                    {
                        "type": "concept",
                        "title": "核心概念",
                        "lede": f"{topic} 是本章的基础结构，先建立直观理解再记公式。",
                        "boxes": [
                            {"title": "定义", "body": f"{topic} 的基本定义与术语。"},
                            {"title": "性质", "body": "与遍历、存储或复杂度相关的关键性质。"},
                        ],
                        "callout": "结合课程资料理解，不要只背名词列表。",
                    },
                    {
                        "type": "example",
                        "title": "例题讲解",
                        "lede": "用一个小例子把概念和操作对应起来。",
                        "callout": f"尝试用一句话解释 {topic} 在算法中的作用。",
                    },
                    {
                        "type": "exercise",
                        "title": "动手练习",
                        "lede": "按步骤完成以下任务：",
                        "tasks": [
                            f"用一句话解释 {topic}",
                            "举一个课程中的具体例子",
                            "指出一个常见易错点",
                        ],
                    },
                    {
                        "type": "quiz",
                        "title": "哪一项描述最准确？",
                        "options": [
                            {"label": "A", "text": f"{topic} 需要结合定义与例子理解", "correct": True, "explain": "与课程资料一致。"},
                            {"label": "B", "text": "可以忽略定义直接做题", "correct": False, "explain": "定义是后续推导的基础。"},
                            {"label": "C", "text": f"{topic} 与课程无关", "correct": False, "explain": "本题围绕当前章节。"},
                        ],
                    },
                    {
                        "type": "summary",
                        "title": "你已经掌握…",
                        "takeaways": [
                            {"title": f"✓ 理解 {topic}", "body": "能用自己的话解释定义。"},
                            {"title": "✓ 联系例题", "body": "能把概念映射到具体操作。"},
                            {"title": "✓ 完成自测", "body": "通过 quiz 检验理解。"},
                        ],
                        "next_hint": "建议回到 Wiki 或练习页继续巩固。",
                    },
                ],
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _generate_grounded_tutor_response(user_input: str) -> str | None:
        if "编号课程证据：" not in user_input or "强制引用规则：" not in user_input:
            return None
        section_match = re.search(
            r"编号课程证据：\s*(.*?)(?:\n\n知识关系：|\Z)",
            user_input,
            flags=re.DOTALL,
        )
        evidence_section = section_match.group(1).strip() if section_match else ""
        evidence = re.findall(
            r"\[S(\d+)\]\s*标题：(.*?)\n页码：.*?\n原文：(.*?)(?=\n\n\[S\d+\]|\Z)",
            evidence_section,
            flags=re.DOTALL,
        )
        if not evidence:
            return "课程资料未找到可靠依据，无法根据当前课程内容回答这个问题。"

        supported_points: list[str] = []
        for number, _title, quote in evidence[:2]:
            concise_quote = re.sub(r"\s+", " ", quote).strip()[:260].rstrip("。！？；; ")
            if concise_quote:
                supported_points.append(f"{concise_quote} [S{number}]。")
        if not supported_points:
            return "课程资料未找到可靠依据，无法根据当前课程内容回答这个问题。"
        return "根据当前课程资料：\n\n" + "\n\n".join(supported_points)

    def _detect_topic(self, user_input: str) -> str:
        for topic in ("栈与队列", "二叉树", "树", "图", "查找", "排序", "线性表", "串", "数组", "数据结构"):
            if topic in user_input:
                return topic
        return "知识点概述"

    def _is_provider_status_question(self, user_input: str) -> bool:
        normalized = user_input.lower()
        provider_keywords = (
            "真实ai",
            "真实 ai",
            "真的ai",
            "真的 ai",
            "真实的大模型",
            "真正的ai",
            "真正的 ai",
            "调用的真",
            "是不是mock",
            "是不是 mock",
            "为什么mock",
            "为什么 mock",
            "provider",
            "mimo",
            "小米",
            "api",
        )
        return any(keyword in normalized for keyword in provider_keywords)

    def _generate_quiz_response(self, user_input: str, topic: str) -> str:
        count = self._detect_count(user_input)
        difficulty = self._detect_difficulty(user_input)
        questions = []
        stems = [
            ("核心理解", f"关于「{topic}」的核心理解，下列说法哪一项最准确？"),
            ("操作过程", f"学习「{topic}」时，为什么要手工模拟一次典型操作？"),
            ("复杂度分析", f"分析「{topic}」相关算法时，最应该关注哪组指标？"),
            ("边界条件", f"使用「{topic}」解决问题时，哪一类情况最容易造成错误？"),
            ("应用迁移", f"把「{topic}」迁移到新题目时，第一步更适合做什么？"),
        ]
        for index in range(count):
            label, stem = stems[index % len(stems)]
            questions.append({
                "question_type": "single_choice",
                "difficulty": difficulty,
                "question_text": stem,
                "options": {
                    "A": "只记忆教材中的一句定义",
                    "B": "把定义、操作过程、复杂度和应用场景联系起来",
                    "C": "跳过边界条件，直接套答案",
                    "D": "只看最终结果，不关注中间状态变化",
                },
                "standard_answer": "B",
                "analysis": f"{label}题用于检查是否能把{topic}的概念、过程和应用联系起来。选 B 更符合数据结构学习的迁移要求。",
                "error_tags": ["概念理解偏差", "过程推演不足"],
            })
        return json.dumps({"questions": questions}, ensure_ascii=False)

    def _detect_count(self, user_input: str) -> int:
        for pattern in (r"数量[：:]\s*(\d+)", r"生成\s*(\d+)\s*道", r"(\d+)\s*道"):
            match = re.search(pattern, user_input)
            if match:
                return max(1, min(20, int(match.group(1))))
        return 5

    def _supervisor_tool_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, object]],
    ) -> ChatResponse | None:
        goal, completed_tools = self._extract_supervisor_state(messages)
        if not goal:
            return None
        from app.agent_runtime import supervisor_intents

        available = {
            str(item.get("function", {}).get("name"))
            for item in tools
            if isinstance(item, dict) and item.get("function", {}).get("name")
        }
        profile_only = supervisor_intents.plan_required_tools(goal, is_profile_update_only=True) == [
            "update_profile_from_dialogue"
        ] and any(
            k in goal
            for k in (
                "请记住",
                "记住我的学习偏好",
                "更新我的画像",
                "记录我的学习偏好",
                "保存我的学习偏好",
            )
        )
        planned = supervisor_intents.plan_required_tools(goal, is_profile_update_only=profile_only)
        for name in planned:
            if name in available and name not in completed_tools:
                return ChatResponse(
                    content="",
                    finish_reason="tool_calls",
                    tool_calls=[
                        ToolCall(
                            id=f"mock_{name}",
                            name=name,
                            arguments={},
                        )
                    ],
                    provider=self.provider_name,
                    model="mock-learning-model",
                )
        return None

    def _extract_supervisor_state(self, messages: list[ChatMessage]) -> tuple[str, set[str]]:
        goal = ""
        completed: set[str] = set()
        for message in reversed(messages):
            content = message.content or ""
            if content.startswith("当前任务状态："):
                try:
                    payload = json.loads(content.removeprefix("当前任务状态："))
                except json.JSONDecodeError:
                    continue
                goal = str(payload.get("goal") or goal)
                for item in payload.get("observations") or []:
                    if isinstance(item, dict) and item.get("success") is True and item.get("tool_name"):
                        completed.add(str(item["tool_name"]))
                break
        if not goal:
            for message in reversed(messages):
                if message.role == "user" and not (message.content or "").startswith("当前任务状态："):
                    goal = message.content or ""
                    break
        return goal, completed

    def _detect_difficulty(self, user_input: str) -> str:
        if "hard" in user_input or "挑战" in user_input:
            return "hard"
        if "easy" in user_input or "入门" in user_input:
            return "easy"
        return "medium"


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
