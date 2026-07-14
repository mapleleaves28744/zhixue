import json

from app.services.html_ppt_courseware_service import HtmlPptCoursewareService


def test_html_ppt_renders_course_module_structure() -> None:
    service = HtmlPptCoursewareService()
    spec = service._fallback_spec("二叉树", {"citations": []})
    rendered = service.render(spec)
    assert "tpl-course-module" in rendered.html
    assert 'class="slide full is-active"' in rendered.html or 'class="slide is-active"' in rendered.html
    assert "slide-number" in rendered.html
    assert "assets/runtime.js" not in rendered.html
    assert rendered.safety_result["passed"] is True


def test_html_ppt_strips_markdown_from_content() -> None:
    service = HtmlPptCoursewareService()
    cleaned = service._clean_text("### 第6章 树与二叉树")
    assert cleaned == "第6章 树与二叉树"
    assert "###" not in cleaned


def test_html_ppt_validate_rejects_external_urls_in_spec() -> None:
    service = HtmlPptCoursewareService()
    result = service.validate_spec({"slides": [{"title": "x", "body": "https://evil.example"}]})
    assert result["passed"] is False


def test_html_ppt_skill_loader_reads_skill_md() -> None:
    service = HtmlPptCoursewareService()
    skill_md = service.skill.skill_md()
    assert "html-ppt" in skill_md.lower()
    assert "course-module" in skill_md


def test_html_ppt_runtime_supports_wheel_and_vertical_keys() -> None:
    service = HtmlPptCoursewareService()
    runtime = service.skill.bundled_runtime()
    assert "ArrowUp" in runtime
    assert "ArrowDown" in runtime
    assert "addEventListener('wheel'" in runtime


def test_html_ppt_normalizes_overlong_cover_copy_before_rendering() -> None:
    service = HtmlPptCoursewareService()
    long_request = "二叉树遍历互动课件：先展示一棵小型二叉树，再逐步演示前序、中序、后序遍历，最后加入两道随堂练习；面向大二期末复习，符合先例子后练习和分步骤讲解偏好，避免大段文字"
    spec = {
        "title": long_request,
        "topic": "二叉树遍历",
        "slides": [
            {"type": "cover", "title": long_request, "subtitle": long_request},
            {"type": "summary", "title": long_request, "takeaways": []},
        ],
    }

    rendered = service.render(spec)

    assert len(rendered.spec["slides"][0]["title"]) <= 24
    assert long_request not in rendered.html
    assert "overflow-wrap:anywhere" in rendered.html


def test_html_ppt_enforces_a_compact_teaching_sequence_for_unbalanced_llm_output() -> None:
    service = HtmlPptCoursewareService()
    spec = {
        "topic": "队列",
        "title": "队列期末复习",
        "slides": [
            {"type": "cover", "title": "队列"},
            {"type": "concept", "title": "概念一", "boxes": [{"title": str(i), "body": "过长正文" * 30} for i in range(6)]},
            {"type": "concept", "title": "概念二"},
        ],
    }

    normalized = service._normalize_spec(spec)

    assert [slide["type"] for slide in normalized["slides"]] == [
        "cover",
        "objectives",
        "concept",
        "example",
        "exercise",
        "quiz",
        "summary",
    ]
    concept_slide = normalized["slides"][2]
    assert len(concept_slide["boxes"]) <= 2
    assert all(len(box["body"]) <= 56 for box in concept_slide["boxes"])
