from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.integrations.openmaic.client import OpenMAICManifest
from app.llm.audio_provider import MockAudioProvider
from app.services.classroom_video_export_service import (
    ClassroomVideoExportService,
    NarrationSegment,
    align_narration_durations,
    build_subtitle_timeline,
    extract_narration_segments,
    resolve_local_openmaic_media_path,
)


def test_align_narration_durations_preserves_audio_and_fills_the_requested_runtime() -> None:
    durations = align_narration_durations([7_840, 9_760, 8_000], target_duration_ms=30_000)

    assert sum(durations) == 30_000
    assert all(actual >= source for actual, source in zip(durations, [7_840, 9_760, 8_000], strict=True))
from app.workers.multimodal_worker import (
    MediaJobReference,
    build_storyboard_manifest,
    build_video_completion_refs,
)


def test_extract_narration_segments_prefers_speech_actions() -> None:
    scenes = [
        {
            "id": "scene_1",
            "order": 1,
            "title": "认识 BFS",
            "actions": [
                {"id": "a1", "type": "spotlight", "target": "title"},
                {
                    "id": "a2",
                    "type": "speech",
                    "text": "广度优先搜索使用队列按层次访问顶点。",
                    "audioUrl": "http://openmaic/api/classroom-media/room/audio/a2.wav",
                },
            ],
        }
    ]

    segments = extract_narration_segments(scenes, fallback_topic="BFS")

    assert segments == [
        NarrationSegment(
            scene_id="scene_1",
            title="认识 BFS",
            text="广度优先搜索使用队列按层次访问顶点。",
            audio_url="http://openmaic/api/classroom-media/room/audio/a2.wav",
        )
    ]


def test_extract_narration_segments_has_readable_fallback() -> None:
    segments = extract_narration_segments(
        [{"id": "scene_1", "order": 1, "title": "BFS 总结", "actions": []}],
        fallback_topic="BFS",
    )

    assert segments[0].title == "BFS 总结"
    assert "BFS 总结" in segments[0].text


def test_build_subtitle_timeline_uses_audio_durations() -> None:
    segments = [
        NarrationSegment("s1", "开场", "第一段字幕", None),
        NarrationSegment("s2", "核心", "第二段字幕", None),
    ]

    timeline = build_subtitle_timeline(segments, [1200, 2300])

    assert timeline == [
        {"index": 1, "start_ms": 0, "end_ms": 1200, "text": "第一段字幕"},
        {"index": 2, "start_ms": 1200, "end_ms": 3500, "text": "第二段字幕"},
    ]


def test_resolve_local_openmaic_media_path_reuses_repo_contained_audio(tmp_path: Path) -> None:
    audio = tmp_path / "room_1" / "audio" / "speech.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"wav")

    resolved = resolve_local_openmaic_media_path(
        "http://127.0.0.1:3001/api/classroom-media/room_1/audio/speech.wav",
        tmp_path,
    )

    assert resolved == audio.resolve()
    assert resolve_local_openmaic_media_path(
        "http://127.0.0.1:3001/api/classroom-media/../secret.txt",
        tmp_path,
    ) is None


def test_build_storyboard_manifest_keeps_chinese_narration_as_speech() -> None:
    manifest = build_storyboard_manifest(
        "BFS（广度优先搜索）",
        [
            {
                "title": "队列与分层访问",
                "narration": "广度优先搜索使用队列按层次访问顶点。",
            }
        ],
    )

    assert manifest.stage["name"] == "BFS（广度优先搜索）"
    assert manifest.scenes[0]["title"] == "队列与分层访问"
    assert manifest.scenes[0]["actions"] == [
        {"type": "speech", "text": "广度优先搜索使用队列按层次访问顶点。"}
    ]


def test_build_storyboard_manifest_preserves_visual_teaching_cues() -> None:
    manifest = build_storyboard_manifest(
        "队列",
        [
            {
                "title": "操作怎么发生",
                "narration": "入队发生在队尾，出队发生在队头。",
                "visual_focus": "步骤拆解",
                "key_points": ["输入", "规则", "结果"],
                "duration_seconds": 10,
            }
        ],
    )

    assert manifest.scenes[0]["visual_focus"] == "步骤拆解"
    assert manifest.scenes[0]["key_points"] == ["输入", "规则", "结果"]
    assert manifest.scenes[0]["duration_seconds"] == 10


def test_build_video_completion_refs_links_asset_to_learning_resource() -> None:
    refs = build_video_completion_refs(
        resource_id="resource-1",
        asset_id="asset-1",
        title="BFS 个性化讲解视频",
        mime_type="video/mp4",
    )

    assert refs == [
        {
            "type": "resource",
            "subtype": "video",
            "id": "resource-1",
            "resource_id": "resource-1",
            "title": "BFS 个性化讲解视频",
        },
        {
            "type": "media_asset",
            "subtype": "video",
            "id": "asset-1",
            "asset_id": "asset-1",
            "resource_id": "resource-1",
            "title": "BFS 个性化讲解视频",
            "mime_type": "video/mp4",
        },
    ]


def test_media_job_reference_snapshots_identifiers_before_async_rendering() -> None:
    job = SimpleNamespace(
        id="job-1",
        user_id="user-1",
        course_id="course-1",
        resource_id="resource-1",
        agent_task_id="task-1",
        conversation_id="conversation-1",
        tool_call_id="call-1",
        provider="local-storyboard",
    )

    reference = MediaJobReference.from_job(job)

    assert reference.user_id == "user-1"
    assert reference.course_id == "course-1"
    assert reference.resource_id == "resource-1"
    assert reference.agent_task_id == "task-1"


@pytest.mark.asyncio
async def test_export_creates_narrated_subtitled_mp4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.classroom_video_export_service.settings.multimodal_storage_dir",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "app.services.classroom_video_export_service.build_audio_provider",
        lambda: MockAudioProvider(),
    )
    manifest = OpenMAICManifest(
        classroom_id="room_export",
        stage={},
        scenes=[
            {
                "id": "scene_1",
                "title": "队列与分层访问",
                "actions": [{"type": "speech", "text": "广度优先搜索使用队列按层次访问顶点。"}],
            }
        ],
    )

    path, size, mime_type, metadata = await ClassroomVideoExportService().export(
        manifest=manifest,
        topic="广度优先搜索 BFS",
    )

    assert Path(path).exists()
    assert size > 1000
    assert mime_type == "video/mp4"
    assert metadata["segments"] == 1
    assert metadata["subtitles_burned_in"] is True
    assert metadata["fps"] == 8
    assert metadata["concatenation_method"] == "chain"
