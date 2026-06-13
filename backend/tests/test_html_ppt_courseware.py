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
