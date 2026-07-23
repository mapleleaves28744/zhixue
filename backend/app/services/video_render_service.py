from __future__ import annotations

import base64
import html
import re
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.llm.audio_provider import build_audio_provider
from app.services.media_storage_service import MediaStorageService


class VideoRenderService:
    def __init__(self) -> None:
        self.storage = MediaStorageService()

    async def render_storyboard_video(
        self,
        *,
        topic: str,
        storyboard: list[dict[str, Any]],
        duration_seconds: int,
    ) -> tuple[str, int, str, dict[str, Any]]:
        try:
            return await self._render_with_moviepy(
                topic=topic,
                storyboard=storyboard,
                duration_seconds=duration_seconds,
            )
        except Exception as exc:
            html_content = self.render_storyboard_html(topic, storyboard, str(exc))
            path, size, mime = self.storage.save_text(text=html_content, asset_type="video_fallback", suffix=".html")
            return path, size, mime, {"fallback": True, "fallback_reason": str(exc), "kind": "storyboard_html"}

    def render_storyboard_html(
        self,
        topic: str,
        storyboard: list[dict[str, Any]],
        note: str = "",
    ) -> str:
        cards = "".join(
            f"<section class='scene'><h2>{html.escape(str(scene.get('title') or topic))}</h2>"
            f"<p>{html.escape(str(scene.get('narration') or scene.get('body') or ''))}</p></section>"
            for scene in storyboard[:8]
        )
        note_html = f"<p class='note'>{html.escape(note)}</p>" if note else ""
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;" />
  <title>{html.escape(topic)} 视频分镜</title>
  <style>
    body {{ margin:0; font-family: system-ui, sans-serif; background:#fff8f0; color:#2b2118; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 32px; }}
    .hero {{ border-radius: 28px; padding: 28px; background: linear-gradient(135deg, #fff, #ffe8c7); margin-bottom: 24px; }}
    .scene {{ margin-top: 16px; padding: 20px; border-radius: 20px; background: #fff; border: 1px solid #f5d7aa; }}
    .note {{ color:#7b4b00; background:#fff2d9; padding:12px; border-radius:14px; }}
  </style>
</head>
<body>
  <main>
    <div class="hero"><h1>{html.escape(topic)}</h1><p>智学工坊 · 个性化讲解分镜预览</p>{note_html}</div>
    {cards}
  </main>
</body>
</html>"""

    async def _render_with_moviepy(
        self,
        *,
        topic: str,
        storyboard: list[dict[str, Any]],
        duration_seconds: int,
    ) -> tuple[str, int, str, dict[str, Any]]:
        from PIL import Image, ImageDraw, ImageFont
        from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips

        frames_dir = Path(settings.multimodal_storage_dir).resolve() / "_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        width, height = 1280, 720
        font_title = _load_cjk_font(ImageFont, 48)
        font_body = _load_cjk_font(ImageFont, 30)
        font_label = _load_cjk_font(ImageFont, 22)

        scenes = storyboard[: max(1, min(8, len(storyboard)))] or [
            {
                "title": topic,
                "narration": f"理解 {topic} 的核心概念。",
                "duration_seconds": duration_seconds,
                "visual_focus": "核心概念",
                "key_points": [f"理解 {topic}", "从例子开始"],
            }
        ]
        out_path = Path(settings.multimodal_storage_dir).resolve() / "video" / f"lesson_{abs(hash(topic))}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        clips: list[Any] = []
        audio_clips: list[Any] = []
        scene_audio_tracks: list[Any] = []
        audio_metadata: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="zhixue-video-") as temp_dir:
            audio_paths, audio_metadata = await self._prepare_narration_audio(scenes, Path(temp_dir))
            for idx, scene in enumerate(scenes):
                image = Image.new("RGB", (width, height), color=(255, 248, 238))
                draw = ImageDraw.Draw(image)
                self._render_scene_frame(
                    draw=draw,
                    topic=topic,
                    scene=scene,
                    index=idx,
                    total=len(scenes),
                    width=width,
                    height=height,
                    title_font=font_title,
                    body_font=font_body,
                    label_font=font_label,
                )
                frame_path = frames_dir / f"frame_{idx}.png"
                image.save(frame_path)
                duration = max(4, int(scene.get("duration_seconds") or 8))
                audio_path = audio_paths[idx]
                if audio_path is not None:
                    audio_clip = AudioFileClip(str(audio_path))
                    audio_clips.append(audio_clip)
                    audio_track = CompositeAudioClip([audio_clip]).with_duration(duration)
                    scene_audio_tracks.append(audio_track)
                    clip = ImageClip(str(frame_path)).with_audio(audio_track).with_duration(duration)
                else:
                    clip = ImageClip(str(frame_path)).with_duration(duration)
                clips.append(clip)

            final = concatenate_videoclips(clips, method="chain")
            try:
                write_kwargs: dict[str, Any] = {
                    "fps": 24,
                    "codec": "libx264",
                    "preset": "veryfast",
                    "logger": None,
                }
                if audio_clips:
                    write_kwargs.update(
                        {
                            "audio_codec": "aac",
                            "temp_audiofile": str(out_path.parent / "lesson_narration.m4a"),
                        }
                    )
                final.write_videofile(str(out_path), **write_kwargs)
            finally:
                final.close()
                for clip in clips:
                    clip.close()
                for track in scene_audio_tracks:
                    track.close()
                for audio_clip in audio_clips:
                    audio_clip.close()
        data = out_path.read_bytes()
        return str(out_path), len(data), "video/mp4", {
            "fallback": False,
            "frames": len(scenes),
            "fps": 24,
            "duration_seconds": sum(int(scene.get("duration_seconds") or 0) for scene in scenes),
            "audio_tracks": audio_metadata,
            "subtitles_burned_in": True,
        }

    async def _prepare_narration_audio(
        self,
        scenes: list[dict[str, Any]],
        temp_dir: Path,
    ) -> tuple[list[Path | None], list[dict[str, Any]]]:
        provider = build_audio_provider()
        paths: list[Path | None] = []
        metadata: list[dict[str, Any]] = []
        for index, scene in enumerate(scenes):
            text = str(scene.get("narration") or scene.get("body") or "").strip()
            if not text:
                paths.append(None)
                metadata.append({"provider": "none", "reason": "empty_narration"})
                continue
            try:
                result = await provider.synthesize(text, response_format="wav", speed=1.02)
                padding = "=" * (-len(result.audio_base64) % 4)
                audio_path = temp_dir / f"narration_{index}.{result.format or 'wav'}"
                audio_path.write_bytes(base64.b64decode(result.audio_base64 + padding))
                paths.append(audio_path)
                metadata.append(
                    {
                        "provider": result.provider,
                        "model": result.model,
                        "duration_ms": result.duration_ms,
                        "fallback": bool((result.raw or {}).get("fallback_used")) or result.provider == "mock_audio",
                    }
                )
            except Exception as exc:
                paths.append(None)
                metadata.append({"provider": "none", "reason": str(exc)[:160]})
        return paths, metadata

    @staticmethod
    def _render_scene_frame(
        *,
        draw: Any,
        topic: str,
        scene: dict[str, Any],
        index: int,
        total: int,
        width: int,
        height: int,
        title_font: Any,
        body_font: Any,
        label_font: Any,
    ) -> None:
        draw.rounded_rectangle((42, 42, width - 42, height - 42), radius=36, fill=(255, 255, 255), outline=(245, 213, 170), width=3)
        draw.rounded_rectangle((78, 72, 274, 112), radius=20, fill=(255, 237, 207))
        draw.text((98, 80), f"第 {index + 1} / {total} 段", fill=(152, 92, 12), font=label_font)
        draw.text((78, 142), str(scene.get("title") or topic)[:28], fill=(45, 35, 24), font=title_font)
        visual_focus = str(scene.get("visual_focus") or "核心概念")[:24]
        draw.rounded_rectangle((78, 212, 78 + 36 + len(visual_focus) * 26, 252), radius=18, fill=(237, 245, 255))
        draw.text((96, 220), visual_focus, fill=(48, 96, 148), font=label_font)

        text = str(scene.get("narration") or scene.get("body") or "")[:160]
        y = 292
        for line in _wrap_zh(text, width=28)[:4]:
            draw.text((82, y), line, fill=(72, 55, 38), font=body_font)
            y += 48

        points = [str(point)[:24] for point in list(scene.get("key_points") or [])[:3]]
        for point_index, point in enumerate(points):
            x = 78 + point_index * 370
            draw.rounded_rectangle((x, 508, x + 334, 578), radius=18, fill=(255, 248, 238), outline=(248, 220, 181), width=2)
            draw.text((x + 20, 529), point, fill=(105, 68, 23), font=label_font)

        progress = (index + 1) / max(total, 1)
        draw.rounded_rectangle((78, 632, width - 78, 646), radius=7, fill=(245, 233, 216))
        draw.rounded_rectangle((78, 632, 78 + int((width - 156) * progress), 646), radius=7, fill=(202, 132, 44))
        draw.text((78, 665), "智学工坊 · 60 秒知识讲解", fill=(120, 80, 20), font=label_font)


def build_storyboard(topic: str, brief: dict[str, Any], duration_seconds: int) -> list[dict[str, Any]]:
    citations = brief.get("citations") or []
    core_fact = _select_core_fact(topic, citations)
    learning_style = str(brief.get("style_hint") or "先看例子，再归纳规律")[:40]
    scene_specs = [
        ("先看一个场景", f"先不背定义。想一想：在真实任务里，{topic} 解决的是什么顺序或组织问题？", "真实场景", ["先想问题", "观察顺序"]),
        ("一句话抓住核心", f"课程资料的关键信息是：{core_fact}", "核心定义", ["抓住规则", "记住关键词"]),
        ("操作怎么发生", f"理解 {topic} 时，把每一步拆成：输入什么、规则怎样作用、结果如何变化。", "步骤拆解", ["输入", "规则", "结果"]),
        ("跟着例子走一遍", f"从一个最小例子开始，边操作边记录状态。{learning_style}。", "最小例子", ["逐步操作", "记录状态"]),
        ("容易混淆的地方", f"不要只记名词。重点核对 {topic} 的操作方向、边界条件和相近概念的区别。", "易错辨析", ["方向", "边界", "区别"]),
        ("30 秒回顾", f"现在用自己的话说出 {topic} 的核心规则，再完成一道小题检验是否真的会用。", "主动回忆", ["复述规则", "完成小题"]),
    ]
    requested_duration = max(len(scene_specs) * 4, int(duration_seconds or 60))
    base, remainder = divmod(requested_duration, len(scene_specs))
    return [
        {
            "title": title,
            "narration": narration,
            "visual_focus": visual_focus,
            "key_points": key_points,
            "duration_seconds": base + (1 if index < remainder else 0),
        }
        for index, (title, narration, visual_focus, key_points) in enumerate(scene_specs)
    ]


def _select_core_fact(topic: str, citations: list[dict[str, Any]]) -> str:
    """从可读的课程证据取一句核心事实；检索噪声不进入课堂字幕。"""
    rejected_markers = ("知识图谱", "关键字", "越界", "章节", "目录", "建议")
    for item in citations[:6]:
        cleaned = _clean_source_text(str(item.get("quote") or ""))
        for sentence in re.split(r"[。！？；;]", cleaned):
            candidate = sentence.strip(" ，、")
            if (
                topic in candidate
                and 12 <= len(candidate) <= 86
                and not any(marker in candidate for marker in rejected_markers)
            ):
                return candidate + "。"
    if "队列" in topic:
        return "队列遵循先进先出规则：入队发生在队尾，出队发生在队头。"
    return f"学习 {topic} 时，先明确它的定义、操作顺序和适用场景。"


def _clean_source_text(value: str) -> str:
    text = re.sub(r"```[\s\S]*?```", "", value)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s*[-*>+]\s*", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


def _wrap_zh(text: str, width: int) -> list[str]:
    return [text[i : i + width] for i in range(0, len(text), width)] or [""]


def _load_cjk_font(image_font: Any, size: int):
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return image_font.truetype(str(candidate), size)
    return image_font.load_default()
