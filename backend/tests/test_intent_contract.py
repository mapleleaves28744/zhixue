from uuid import uuid4

from app.agent_runtime.intent_contract import (
    build_intent_frame, follow_up_topic, looks_like_topic_answer, subtask_progress,
)


def test_contract_keeps_same_tool_for_distinct_topics() -> None:
    frame = build_intent_frame(
        goal="给栈出练习题，给队列出练习题", request_message_id=uuid4(),
    ).model_dump(mode="json")

    assert frame["schema_version"] == "v1"
    assert frame["mode"] == "execute"
    assert [item["topic"] for item in frame["tasks"]] == ["栈", "队列"]
    assert [item["tools"] for item in frame["tasks"]] == [["generate_quiz"], ["generate_quiz"]]

    result = {
        "tool_calls": [
            {"id": "c1", "name": "generate_quiz", "arguments": {"topic": "栈"}},
            {"id": "c2", "name": "generate_quiz", "arguments": {"topic": "队列"}},
        ],
        "observations": [
            {"tool_call_id": "c1", "success": True, "artifact_refs": [{"id": "quiz-1"}]},
        ],
    }
    progress = subtask_progress(frame, result)
    assert [item["status"] for item in progress] == ["succeeded", "pending"]
    result["observations"].append(
        {"tool_call_id": "c2", "success": True, "artifact_refs": [{"id": "quiz-2"}]},
    )
    assert [item["status"] for item in subtask_progress(frame, result)] == ["succeeded", "succeeded"]


def test_contract_respects_excluded_tool() -> None:
    frame = build_intent_frame(
        goal="制作二叉树 PPT 和队列思维导图", request_message_id=uuid4(),
        skip_tools=["generate_interactive_courseware"],
    )

    assert frame.exclusions == ["generate_interactive_courseware"]
    assert all("generate_interactive_courseware" not in task.tools for task in frame.tasks)


def test_transcription_accepts_nonempty_text_without_artifact() -> None:
    frame = {
        "tasks": [{"id": "s1", "topic": "语音", "tools": ["transcribe_audio"]}],
    }
    result = {
        "tool_calls": [{"id": "c1", "name": "transcribe_audio", "arguments": {}}],
        "observations": [{
            "tool_call_id": "c1", "tool_name": "transcribe_audio", "success": True,
            "output": {"text": "这是一条语音笔记"}, "artifact_refs": [],
        }],
    }

    assert subtask_progress(frame, result)[0]["status"] == "succeeded"


def test_follow_up_quiz_uses_single_previous_topic() -> None:
    goal = "再给我五道同类题"
    topic = follow_up_topic(goal=goal, previous_question="给栈出练习题")
    frame = build_intent_frame(
        goal=goal, request_message_id=uuid4(), fallback_topic=topic,
    )

    assert topic == "栈"
    assert frame.tasks[0].topic == "栈"
    assert frame.tasks[0].tools == ["generate_quiz"]
    assert follow_up_topic(goal=goal, previous_question="栈和队列各出练习题") is None


def test_missing_follow_up_topic_requests_clarification() -> None:
    frame = build_intent_frame(
        goal="再给我五道同类题", request_message_id=uuid4(),
    )

    assert frame.mode == "clarify"
    assert frame.tasks == []
    assert frame.unresolved_slots == ["topic"]
    assert looks_like_topic_answer("二叉树的非递归遍历")
    assert not looks_like_topic_answer("天气怎么样？")


def test_retrieval_and_review_accept_valid_structured_results_without_new_artifact() -> None:
    for name, output in [("search_course_knowledge", {"items": []}),
                         ("review_artifacts", {"pass": False, "issues": ["需要补充原文"]}),
                         ("reflect_learning_memory", {"memories": []})]:
        frame = {"tasks": [{"id": "s1", "topic": "栈", "tools": [name]}]}
        result = {"tool_calls": [{"id": "c1", "name": name}], "observations": [
            {"tool_call_id": "c1", "tool_name": name, "success": True, "output": output}]}
        assert subtask_progress(frame, result)[0]["status"] == "succeeded"
        result["observations"][0]["output"] = {}
        assert subtask_progress(frame, result)[0]["status"] != "succeeded"
