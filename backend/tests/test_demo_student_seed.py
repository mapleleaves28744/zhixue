from __future__ import annotations

import importlib


def test_demo_blueprint_covers_main_learning_loop() -> None:
    module = importlib.import_module("scripts.init_demo_student_data")

    blueprint = module.build_demo_blueprint()
    resource_types = {item["resource_type"] for item in blueprint["resources"]}
    event_types = set(blueprint["learning_events"])

    assert module.demo_course_payload()["course_code"] == "DS-DEMO"
    assert {"explanation", "mindmap", "diagram", "flashcard"}.issubset(resource_types)
    assert {
        "wiki_read",
        "tutor_ask",
        "quiz_start",
        "quiz_complete",
        "profile_updated",
        "diagnosis_generated",
        "recommendation_view",
    }.issubset(event_types)
    assert len(blueprint["knowledge_points"]) >= 3
    assert len(blueprint["wiki_pages"]) >= 2


def test_demo_blueprint_includes_all_supported_quiz_types() -> None:
    module = importlib.import_module("scripts.init_demo_student_data")

    question_types = {item["question_type"] for item in module.build_demo_blueprint()["quiz_questions"]}

    assert {
        "single_choice",
        "multiple_choice",
        "true_false",
        "fill_blank",
        "short_answer",
        "coding",
    }.issubset(question_types)
