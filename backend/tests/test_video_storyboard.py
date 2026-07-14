from app.services.video_render_service import build_storyboard
from pathlib import Path


def test_video_storyboard_is_a_concise_classroom_explanation() -> None:
    scenes = build_storyboard(
        "队列",
        {
            "citations": [
                {"quote": "队列遵循先进先出原则，入队发生在队尾，出队发生在队头。"},
            ],
            "style_hint": "先例子后定义，适合初学者",
        },
        60,
    )

    assert [scene["title"] for scene in scenes] == [
        "先看一个场景",
        "一句话抓住核心",
        "操作怎么发生",
        "跟着例子走一遍",
        "容易混淆的地方",
        "30 秒回顾",
    ]
    assert all(len(scene["narration"]) <= 120 for scene in scenes)
    assert "先进先出" in scenes[1]["narration"]


def test_video_storyboard_has_timing_and_visual_guidance_for_each_scene() -> None:
    scenes = build_storyboard("队列", {"citations": [], "style_hint": "先例子后定义"}, 60)

    assert sum(scene["duration_seconds"] for scene in scenes) == 60
    assert all(scene["visual_focus"] for scene in scenes)
    assert all(1 <= len(scene["key_points"]) <= 3 for scene in scenes)


def test_video_storyboard_rejects_markdown_noise_and_uses_a_topic_fact() -> None:
    scenes = build_storyboard(
        "队列",
        {
            "citations": [
                {
                    "quote": "### 第3章 栈与队列\n- 重复关键字或越界位置\n- **知识图谱建议**",
                },
            ],
            "style_hint": "先例子后定义",
        },
        60,
    )

    core_scene = scenes[1]["narration"]
    assert "###" not in core_scene
    assert "**" not in core_scene
    assert "知识图谱建议" not in core_scene
    assert "先进先出" in core_scene


def test_video_renderer_keeps_the_scene_duration_after_attaching_audio() -> None:
    source = Path("app/services/video_render_service.py").read_text(encoding="utf-8")

    assert "ImageClip(str(frame_path)).with_audio(audio_track).with_duration(duration)" in source


def test_video_renderer_pads_short_audio_to_the_scene_duration() -> None:
    source = Path("app/services/video_render_service.py").read_text(encoding="utf-8")

    assert "CompositeAudioClip([audio_clip]).with_duration(duration)" in source
