"""ProfileService 单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.profile_service import ProfileService


def test_course_summary_formats_weak_points_and_errors() -> None:
    svc = ProfileService(db=None)  # type: ignore[arg-type]
    profile = SimpleNamespace(
        learning_goal="掌握二叉树遍历",
        weak_points=[
            {"knowledge_name": "递归", "confidence": 0.88},
            {"knowledge_name": "栈", "confidence": 0.85},
        ],
        error_patterns=[
            {"pattern": "边界条件遗漏", "confidence": 0.84},
        ],
    )
    summary = svc._course_summary(profile)
    assert "课程目标：掌握二叉树遍历" in summary
    assert "薄弱点：递归、栈" in summary
    assert "常见错误：边界条件遗漏" in summary
    assert "knowledge_name" not in summary


def test_course_summary_empty_returns_default() -> None:
    svc = ProfileService(db=None)  # type: ignore[arg-type]
    profile = SimpleNamespace(learning_goal=None, weak_points=[], error_patterns=[])
    summary = svc._course_summary(profile)
    assert summary == "当前课程画像正在积累真实学习证据。"
