"""Supervisor 意图路由回归测试 — 防止工具误匹配。"""

from __future__ import annotations

import pytest

from app.agent_runtime import supervisor_intents
from app.agent_runtime.supervisor import MiMoSupervisor
from app.llm.schemas import ChatResponse, ToolCall


class DirectCompleteProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content='{"status":"complete","summary":"直接完成","final_answer":"这是文字回答。"}'
        )


@pytest.mark.parametrize(
    ("goal", "must_include", "must_exclude"),
    [
        ("生成讲解队列的语音", ["generate_explanation", "synthesize_speech"], []),
        ("生成队列讲解视频", ["generate_lesson_video"], ["synthesize_speech"]),
        ("为 BFS 生成沉浸课堂", ["generate_immersive_classroom"], ["generate_lesson_video"]),
        ("一键生成数据结构课程", ["generate_immersive_classroom"], ["generate_lesson_video"]),
        ("生成知识点讲解视频和沉浸课堂", ["generate_immersive_classroom"], ["generate_lesson_video"]),
        ("生成一份练习题", ["generate_quiz"], ["generate_explanation"]),
        ("制定学习计划并生成练习题", ["generate_learning_path", "generate_quiz"], []),
        ("讲解一下队列是什么", ["answer_course_question"], ["generate_explanation"]),
        ("画一张栈的入栈出栈流程图", ["generate_diagram"], ["generate_educational_image"]),
        ("给队列概念配一张教学插图", ["generate_educational_image"], []),
        ("生成讲解队列的知识卡片", ["generate_educational_image"], ["generate_explanation"]),
        ("识别这段语音并转成文字", ["transcribe_audio"], ["synthesize_speech"]),
        ("把这段文字朗读出来", ["synthesize_speech"], ["transcribe_audio", "generate_explanation"]),
    ],
)
def test_plan_required_tools_avoids_common_collisions(
    goal: str,
    must_include: list[str],
    must_exclude: list[str],
) -> None:
    tools = supervisor_intents.plan_required_tools(goal, is_profile_update_only=False)
    for name in must_include:
        assert name in tools, f"{goal!r} 应包含 {name}，实际 {tools}"
    for name in must_exclude:
        assert name not in tools, f"{goal!r} 不应包含 {name}，实际 {tools}"


@pytest.mark.parametrize(
    ("goal", "deliverable"),
    [
        ("生成讲解队列的语音", "synthesize_speech"),
        ("生成队列讲解视频", "generate_lesson_video"),
        ("为 BFS 生成沉浸课堂", "generate_immersive_classroom"),
        ("生成一份练习题", "generate_quiz"),
        ("生成讲解资料", "generate_explanation"),
        ("应用最新的一条自进化策略", "apply_evolution_strategy"),
        ("应用自进化策略", "apply_evolution_strategy"),
    ],
)
def test_required_deliverables(goal: str, deliverable: str) -> None:
    assert deliverable in supervisor_intents.required_deliverables(goal)


@pytest.mark.asyncio
async def test_supervisor_blocks_text_only_completion_for_video_goal() -> None:
    supervisor = MiMoSupervisor(provider=DirectCompleteProvider())
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in ("search_course_knowledge", "generate_lesson_video")
    ]
    decision = await supervisor.decide(
        {
            "goal": "生成二叉树的讲解视频",
            "messages": [],
            "observations": [{"success": True, "tool_name": "search_course_knowledge"}],
            "citations": [{"title": "资料"}],
            "tool_calls": [],
        },
        tools,
    )
    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "generate_lesson_video"


@pytest.mark.asyncio
async def test_supervisor_llm_first_allows_plain_qa_without_keyword_injection() -> None:
    supervisor = MiMoSupervisor(provider=DirectCompleteProvider())
    decision = await supervisor.decide(
        {
            "goal": "解释一下广度优先搜索的核心思想",
            "messages": [],
            "observations": [],
            "tool_calls": [],
            "tool_call_count": 0,
        },
        [
            {
                "type": "function",
                "function": {
                    "name": "search_course_knowledge",
                    "description": "检索",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )
    assert decision.status == "complete"
    assert decision.tool_calls == []


@pytest.mark.asyncio
async def test_supervisor_native_tool_calls_not_overridden_by_keywords() -> None:
    class WrongToolProvider:
        async def chat(self, messages, **kwargs):
            return ChatResponse(
                content="",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(id="call_q", name="answer_course_question", arguments={"question": "test"}),
                ],
            )

    supervisor = MiMoSupervisor(provider=WrongToolProvider())
    decision = await supervisor.decide(
        {
            "goal": "生成讲解队列的语音",
            "messages": [],
            "observations": [],
            "tool_calls": [],
        },
        [
            {
                "type": "function",
                "function": {"name": name, "description": name, "parameters": {"type": "object"}},
            }
            for name in ("answer_course_question", "synthesize_speech", "generate_explanation")
        ],
    )
    assert decision.tool_calls[0].name == "answer_course_question"


@pytest.mark.asyncio
async def test_supervisor_stops_after_knowledge_card_image_generated() -> None:
    class RegenerateImageProvider:
        async def chat(self, messages, **kwargs):
            return ChatResponse(
                content="",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_img2",
                        name="generate_educational_image",
                        arguments={"topic": "队列"},
                    ),
                ],
            )

    supervisor = MiMoSupervisor(provider=RegenerateImageProvider())
    decision = await supervisor.decide(
        {
            "goal": "生成讲解队列的知识卡片",
            "messages": [],
            "observations": [
                {
                    "success": True,
                    "tool_name": "generate_educational_image",
                    "output": {"generation_mode": "image"},
                }
            ],
            "artifacts": [
                {
                    "type": "media_asset",
                    "subtype": "image",
                    "title": "队列知识卡片",
                    "mime_type": "image/png",
                }
            ],
            "tool_calls": [],
        },
        [
            {
                "type": "function",
                "function": {
                    "name": "generate_educational_image",
                    "description": "插图",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )
    assert decision.status == "complete"
    assert decision.tool_calls == []


@pytest.mark.asyncio
async def test_supervisor_blocks_text_only_completion_for_quiz_goal() -> None:
    supervisor = MiMoSupervisor(provider=DirectCompleteProvider())
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in ("generate_quiz",)
    ]
    decision = await supervisor.decide(
        {"goal": "生成一份关于队列的练习题", "messages": [], "observations": [], "tool_calls": []},
        tools,
    )
    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "generate_quiz"
