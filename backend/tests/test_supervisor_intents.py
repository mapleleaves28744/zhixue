"""Supervisor 意图路由回归测试 — 防止工具误匹配。"""

from __future__ import annotations

import pytest

from app.agent_runtime import supervisor_intents
from app.agent_runtime.supervisor_completion import format_search_output_answer
from app.agent_runtime.supervisor_policy import safe_arguments
from app.agent_runtime.supervisor import MiMoSupervisor
from app.llm.schemas import ChatResponse, ToolCall


class DirectCompleteProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content='{"status":"complete","summary":"直接完成","final_answer":"这是文字回答。"}'
        )


def test_completion_formats_empty_course_search() -> None:
    answer = format_search_output_answer("search_course_knowledge", {"items": []}, "栈")

    assert "未找到相关结果" in answer


def test_safe_arguments_compatibility_for_courseware_ppt_goal() -> None:
    goal = "请做一份二叉树讲解 PPT"

    expected = safe_arguments("generate_interactive_courseware", {}, goal)
    actual = MiMoSupervisor(provider=object())._safe_arguments(
        "generate_interactive_courseware", {}, goal
    )

    assert actual == expected
    assert actual["topic"] == expected["topic"]
    assert actual["interaction_type"] == "stepper"


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
        ("生成图和二叉树的讲解ppt", ["generate_interactive_courseware"], ["generate_lesson_video"]),
        ("做一份二叉树 slides", ["generate_interactive_courseware"], ["generate_lesson_video"]),
        ("生成栈的网页幻灯片", ["generate_interactive_courseware"], ["generate_lesson_video"]),
        ("生成二叉树ppt和队列思维导图", ["generate_interactive_courseware", "generate_mindmap"], ["generate_lesson_video"]),
        ("帮我做二叉树幻灯片，再画一张队列的流程图", ["generate_interactive_courseware", "generate_diagram"], []),
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
async def test_supervisor_intent_first_routes_ppt_without_llm() -> None:
    class ShouldNotCallProvider:
        async def chat(self, messages, **kwargs):
            raise AssertionError("明确 PPT 意图时不应再让 LLM 自由选工具")

    supervisor = MiMoSupervisor(provider=ShouldNotCallProvider())
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in ("search_course_knowledge", "generate_interactive_courseware", "generate_lesson_video")
    ]
    decision = await supervisor.decide(
        {
            "goal": "生成图和二叉树的讲解ppt",
            "messages": [],
            "observations": [],
            "tool_calls": [],
            "tool_call_count": 0,
        },
        tools,
    )
    assert decision.status == "continue"
    assert any(call.name == "generate_interactive_courseware" for call in decision.tool_calls)
    assert all(call.name != "generate_lesson_video" for call in decision.tool_calls)


@pytest.mark.asyncio
async def test_supervisor_corrects_wrong_video_tool_for_ppt_goal() -> None:
    class WrongVideoProvider:
        async def chat(self, messages, **kwargs):
            return ChatResponse(
                content="",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_video",
                        name="generate_lesson_video",
                        arguments={"topic": "图和二叉树"},
                    ),
                ],
            )

    supervisor = MiMoSupervisor(provider=WrongVideoProvider())
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in (
            "search_course_knowledge",
            "generate_lesson_video",
            "generate_interactive_courseware",
        )
    ]
    decision = await supervisor.decide(
        {
            "goal": "生成图和二叉树的讲解ppt",
            "messages": [],
            "observations": [{"success": True, "tool_name": "search_course_knowledge", "output": {}}],
            "tool_calls": [],
            "tool_call_count": 1,
        },
        tools,
    )
    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "generate_interactive_courseware"


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
            "tool_call_count": 1,
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


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        (
            "生成二叉树ppt和队列思维导图",
            {
                "generate_interactive_courseware": "二叉树",
                "generate_mindmap": "队列",
            },
        ),
        (
            "帮我做二叉树幻灯片，再画一张队列的流程图",
            {
                "generate_interactive_courseware": "二叉树",
                "generate_diagram": "队列",
            },
        ),
    ],
)
def test_parse_tool_topics_for_multi_intent(goal: str, expected: dict[str, str]) -> None:
    topics = supervisor_intents.parse_tool_topics(goal)
    for tool, topic in expected.items():
        assert topics.get(tool) == topic, f"{goal!r} -> {topics}"


@pytest.mark.asyncio
async def test_supervisor_intent_first_routes_multi_intent_with_topics() -> None:
    class ShouldNotCallProvider:
        async def chat(self, messages, **kwargs):
            raise AssertionError("多意图明确时不应交给 LLM 自由选工具")

    supervisor = MiMoSupervisor(provider=ShouldNotCallProvider())
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in (
            "search_course_knowledge",
            "generate_interactive_courseware",
            "generate_mindmap",
            "generate_lesson_video",
        )
    ]
    tool_topics = supervisor_intents.parse_tool_topics("生成二叉树ppt和队列思维导图")
    decision = await supervisor.decide(
        {
            "goal": "生成二叉树ppt和队列思维导图",
            "messages": [],
            "observations": [],
            "tool_calls": [],
            "tool_call_count": 0,
            "tool_topics": tool_topics,
        },
        tools,
    )
    assert decision.status == "continue"
    names = [call.name for call in decision.tool_calls]
    assert "generate_interactive_courseware" in names
    assert "generate_mindmap" in names
    courseware = next(call for call in decision.tool_calls if call.name == "generate_interactive_courseware")
    mindmap = next(call for call in decision.tool_calls if call.name == "generate_mindmap")
    assert courseware.arguments.get("topic") == "二叉树"
    assert mindmap.arguments.get("topic") == "队列"
