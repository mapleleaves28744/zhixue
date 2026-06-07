from __future__ import annotations

from app.main import app
from app.services.profile_service import ProfileService


def test_profile_dialogue_signal_extraction_builds_evidence_ready_profile() -> None:
    service = ProfileService.__new__(ProfileService)

    signals = service._extract_dialogue_profile_signals(
        "我是软件工程大二学生，学习目标是期末拿到 85 分以上。"
        "我递归和二叉树遍历比较薄弱，经常漏掉边界条件。"
        "我喜欢 Python 代码示例、分步骤讲解和短一点的总结。"
    )

    assert signals["major"] == "软件工程"
    assert signals["grade"] == "大二"
    assert "85" in signals["learning_goal"]
    assert signals["preferences"]["answer_length"] == "short"
    assert signals["preferences"]["explanation_style"] == "code_first"
    assert "python_code" in signals["preferences"]["resource_preferences"]
    assert [item["knowledge_name"] for item in signals["weak_points"]] == ["递归", "二叉树遍历"]
    assert signals["error_patterns"][0]["pattern"] == "边界条件遗漏"


def test_profile_dialogue_dimensions_keep_source_evidence() -> None:
    service = ProfileService.__new__(ProfileService)
    evidence = service._build_dialogue_evidence(
        source_message_id="msg-1",
        dialogue_text="我喜欢图示化解释，也希望系统记住我正在补弱图的最短路径。",
    )
    signals = service._extract_dialogue_profile_signals(evidence["quote"])

    summary = service._build_dialogue_profile_summary(
        existing={},
        signals=signals,
        evidence=evidence,
    )

    dimensions = summary["dimensions"]
    assert dimensions["explanation_style"]["value"] == "visual_first"
    assert dimensions["weak_points"]["items"][0]["knowledge_name"] == "图的最短路径"
    assert dimensions["explanation_style"]["evidence"][0]["source_message_id"] == "msg-1"
    assert summary["source_count"] == 1


def test_phase4_profile_dialogue_api_route_registered() -> None:
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/student/profile/dialogue-ingest" in routes
