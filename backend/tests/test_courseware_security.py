from app.services.courseware_service import CoursewareService


def test_courseware_rejects_external_url():
    service = CoursewareService()
    result = service.validate_spec({"title": "x", "steps": [{"body": "https://evil.example"}]})
    assert result["passed"] is False


def test_courseware_render_safe_template():
    service = CoursewareService()
    spec = service.build_spec(topic="BFS", interaction_type="stepper", brief={"citations": []})
    rendered = service.render(spec)
    assert "default-src 'none'" in rendered.html
    assert "fetch(" not in rendered.html.lower()
