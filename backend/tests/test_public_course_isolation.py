from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.course_service import CourseService
from app.services.material_service import MaterialService


def _user(*, role: str = "student", user_id=None):
    return SimpleNamespace(id=user_id or uuid4(), role=role)


def _course(*, owner_id, visibility: str = "private", status: str = "active"):
    return SimpleNamespace(owner_id=owner_id, visibility=visibility, status=status)


def _material(*, uploaded_by):
    return SimpleNamespace(uploaded_by=uploaded_by)


def test_public_template_course_is_readable_but_not_content_writable_for_other_students() -> None:
    service = CourseService.__new__(CourseService)
    owner = _user()
    other_student = _user()
    public_course = _course(owner_id=owner.id, visibility="public_template")

    assert service.can_read_course(public_course, other_student) is True
    assert service.can_write_personal_learning_data(public_course, other_student) is True
    assert service.can_write_course_content(public_course, other_student) is False


def test_private_course_is_hidden_from_other_students() -> None:
    service = CourseService.__new__(CourseService)
    owner = _user()
    other_student = _user()
    private_course = _course(owner_id=owner.id, visibility="private")

    assert service.can_read_course(private_course, owner) is True
    assert service.can_write_course_content(private_course, owner) is True
    assert service.can_read_course(private_course, other_student) is False
    assert service.can_write_personal_learning_data(private_course, other_student) is False


def test_admin_can_read_and_write_any_course() -> None:
    service = CourseService.__new__(CourseService)
    owner = _user()
    admin = _user(role="admin")
    private_course = _course(owner_id=owner.id, visibility="private")

    assert service.can_read_course(private_course, admin) is True
    assert service.can_write_course_content(private_course, admin) is True


def test_public_builtin_material_is_readable_but_not_writable_for_students() -> None:
    service = MaterialService.__new__(MaterialService)
    owner = _user()
    student = _user()
    public_course = _course(owner_id=owner.id, visibility="public_template")
    public_material = _material(uploaded_by=owner.id)

    assert service._can_read_material(public_material, public_course, student) is True
    assert service._can_write_material(public_material, public_course, student) is False


def test_student_overlay_material_under_public_course_is_private_and_writable() -> None:
    service = MaterialService.__new__(MaterialService)
    owner = _user()
    student_a = _user()
    student_b = _user()
    public_course = _course(owner_id=owner.id, visibility="public_template")
    personal_material = _material(uploaded_by=student_a.id)

    assert service._can_read_material(personal_material, public_course, student_a) is True
    assert service._can_write_material(personal_material, public_course, student_a) is True
    assert service._can_read_material(personal_material, public_course, student_b) is False
    assert service._can_write_material(personal_material, public_course, student_b) is False
