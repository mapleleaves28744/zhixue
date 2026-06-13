from __future__ import annotations

from uuid import uuid4

from app.schemas.multimodal import ImmersiveClassroomGenerateRequest
from app.services.immersive_classroom_service import ImmersiveClassroomService
from app.workers.immersive_classroom_worker import build_classroom_descriptor, map_openmaic_progress


def test_classroom_request_defaults_to_narrated_video_export() -> None:
    payload = ImmersiveClassroomGenerateRequest(course_id=uuid4(), topic="BFS")

    assert payload.generate_video_export is True
    assert payload.enable_images is True
    assert payload.enable_tts is True


def test_classroom_context_is_personalized_and_excludes_private_fields() -> None:
    brief = {
        "profile": {
            "major": "软件工程",
            "grade": "大二",
            "learning_goal": "掌握图遍历",
            "weak_points": [{"knowledge_name": "队列"}],
            "email": "private@example.com",
            "jwt": "secret-token",
            "strategy_summary": {"private_memory": "不要发送完整记忆"},
        },
        "style_hint": "使用图解和分步骤讲解",
        "citations": [
            {
                "title": "数据结构讲义",
                "page_no": 12,
                "quote": "广度优先搜索使用队列按层次访问顶点。",
            }
        ],
    }

    requirement, context_text = ImmersiveClassroomService.build_classroom_context(
        course_title="数据结构",
        topic="BFS",
        learning_goal="适合初学者并强调队列变化",
        brief=brief,
    )

    combined = f"{requirement}\n{context_text}"
    assert "数据结构" in combined
    assert "BFS" in combined
    assert "队列" in combined
    assert "图解和分步骤" in combined
    assert "数据结构讲义" in combined
    assert "private@example.com" not in combined
    assert "secret-token" not in combined
    assert "不要发送完整记忆" not in combined


def test_classroom_asset_ref_has_launchable_subtype() -> None:
    ref = ImmersiveClassroomService.classroom_asset_ref(
        asset_id="asset-1",
        title="BFS 沉浸课堂",
        scenes_count=6,
        citation_count=3,
        personalized_reason="图解优先",
    )

    assert ref == {
        "type": "media_asset",
        "subtype": "immersive_classroom",
        "asset_id": "asset-1",
        "title": "BFS 沉浸课堂",
        "mime_type": "application/vnd.zhixue.openmaic-classroom+json",
        "scenes_count": 6,
        "citation_count": 3,
        "personalized_reason": "图解优先",
    }


def test_openmaic_progress_maps_to_zhixue_stages() -> None:
    assert map_openmaic_progress("generating_outlines", 15) == ("generating_outlines", 15)
    assert map_openmaic_progress("generating_tts", 94) == ("generating_tts", 94)
    assert map_openmaic_progress("completed", 100) == ("persisting_classroom", 100)


def test_classroom_descriptor_keeps_traceable_metadata() -> None:
    descriptor = build_classroom_descriptor(
        classroom_id="room_1",
        title="BFS 沉浸课堂",
        scenes_count=7,
        citations=[{"title": "数据结构讲义"}],
        personalized_reason="图解优先",
    )

    assert descriptor["classroom_id"] == "room_1"
    assert descriptor["scenes_count"] == 7
    assert descriptor["citation_count"] == 1
    assert descriptor["personalized_reason"] == "图解优先"
