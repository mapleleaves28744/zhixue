from __future__ import annotations

import asyncio
import base64
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.integrations.openmaic.client import OpenMAICClient, OpenMAICManifest
from app.llm.audio_provider import build_audio_provider
from app.services.media_storage_service import MediaStorageService

NARRATED_VIDEO_FPS = 8
OPENMAIC_CLASSROOMS_ROOT = Path(__file__).resolve().parents[3] / "third_party" / "openmaic" / "data" / "classrooms"


@dataclass(frozen=True)
class NarrationSegment:
    scene_id: str
    title: str
    text: str
    audio_url: str | None
    target_duration_ms: int | None = None
    visual_focus: str = "核心概念"
    key_points: tuple[str, ...] = ()


def extract_narration_segments(
    scenes: list[dict[str, Any]],
    *,
    fallback_topic: str,
) -> list[NarrationSegment]:
    segments: list[NarrationSegment] = []
    for index, scene in enumerate(scenes, start=1):
        raw_target_seconds = scene.get("duration_seconds")
        try:
            target_duration_ms = max(0, int(float(raw_target_seconds) * 1000))
        except (TypeError, ValueError):
            target_duration_ms = None
        title = str(
            scene.get("title")
            or (scene.get("content") or {}).get("title")
            or f"{fallback_topic} · 场景 {index}"
        )
        visual_focus = str(scene.get("visual_focus") or "核心概念").strip()[:24]
        key_points = tuple(
            str(point).strip()[:24]
            for point in list(scene.get("key_points") or [])[:3]
            if str(point).strip()
        )
        speech_actions = [
            action
            for action in list(scene.get("actions") or [])
            if isinstance(action, dict) and action.get("type") == "speech" and str(action.get("text") or "").strip()
        ]
        if speech_actions:
            for action in speech_actions:
                segments.append(
                    NarrationSegment(
                        scene_id=str(scene.get("id") or f"scene_{index}"),
                        title=title[:120],
                        text=str(action.get("text") or "").strip()[:1200],
                        audio_url=str(action.get("audioUrl")) if action.get("audioUrl") else None,
                        target_duration_ms=target_duration_ms,
                        visual_focus=visual_focus,
                        key_points=key_points,
                    )
                )
            continue
        segments.append(
            NarrationSegment(
                scene_id=str(scene.get("id") or f"scene_{index}"),
                title=title[:120],
                text=f"本节课堂场景：{title}。请结合画面理解这一知识点。",
                audio_url=None,
                target_duration_ms=target_duration_ms,
                visual_focus=visual_focus,
                key_points=key_points,
            )
        )
    return segments[:40] or [
        NarrationSegment(
            scene_id="fallback",
            title=fallback_topic,
            text=f"本视频讲解 {fallback_topic} 的核心概念。",
            audio_url=None,
        )
    ]


def align_narration_durations(audio_durations_ms: list[int], *, target_duration_ms: int) -> list[int]:
    """保留全部配音，并在目标总时长更长时把剩余时间均匀留给画面和字幕。"""
    durations = [max(1, int(value)) for value in audio_durations_ms]
    if not durations or target_duration_ms <= sum(durations):
        return durations
    padding, remainder = divmod(target_duration_ms - sum(durations), len(durations))
    return [duration + padding + (1 if index < remainder else 0) for index, duration in enumerate(durations)]


def build_subtitle_timeline(
    segments: list[NarrationSegment],
    durations_ms: list[int],
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    cursor = 0
    for index, (segment, duration_ms) in enumerate(zip(segments, durations_ms, strict=True), start=1):
        duration = max(1, int(duration_ms))
        timeline.append(
            {
                "index": index,
                "start_ms": cursor,
                "end_ms": cursor + duration,
                "text": segment.text,
            }
        )
        cursor += duration
    return timeline


def resolve_local_openmaic_media_path(audio_url: str, classrooms_root: Path = OPENMAIC_CLASSROOMS_ROOT) -> Path | None:
    parts = Path(urlparse(audio_url).path).parts
    try:
        marker = parts.index("classroom-media")
    except ValueError:
        return None
    relative_parts = parts[marker + 1 :]
    if not relative_parts or any(part in {"", ".", ".."} for part in relative_parts):
        return None
    root = classrooms_root.resolve()
    candidate = root.joinpath(*relative_parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


class ClassroomVideoExportService:
    def __init__(self, client: OpenMAICClient | None = None) -> None:
        self.client = client or OpenMAICClient()
        self.storage = MediaStorageService()

    async def export(
        self,
        *,
        manifest: OpenMAICManifest,
        topic: str,
    ) -> tuple[str, int, str, dict[str, Any]]:
        segments = extract_narration_segments(manifest.scenes, fallback_topic=topic)
        work_root = Path(settings.multimodal_storage_dir).resolve() / "_classroom_exports"
        work_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work_root) as temp_dir:
            temp = Path(temp_dir)
            prepared_audio = await asyncio.gather(
                *(self._prepare_audio(segment, temp, index) for index, segment in enumerate(segments))
            )
            audio_paths = [item[0] for item in prepared_audio]
            audio_durations_ms = [item[1] for item in prepared_audio]
            requested_duration_ms = sum(segment.target_duration_ms or 0 for segment in segments)
            durations_ms = align_narration_durations(
                audio_durations_ms,
                target_duration_ms=requested_duration_ms,
            )
            audio_sources = [item[2] for item in prepared_audio]
            timeline = build_subtitle_timeline(segments, durations_ms)
            output = temp / "classroom_lesson.mp4"
            self._render_video(
                topic=topic,
                segments=segments,
                audio_paths=audio_paths,
                durations_ms=durations_ms,
                output=output,
            )
            path, size, mime = self.storage.save_bytes(
                data=output.read_bytes(),
                asset_type="video",
                suffix=".mp4",
            )
        return path, size, mime, {
            "mode": "openmaic_narrated_export",
            "classroom_id": manifest.classroom_id,
            "segments": len(segments),
            "duration_ms": sum(durations_ms),
            "subtitle_timeline": timeline,
            "audio_sources": audio_sources,
            "subtitles_burned_in": True,
            "fps": NARRATED_VIDEO_FPS,
            "concatenation_method": "chain",
        }

    async def _prepare_audio(
        self,
        segment: NarrationSegment,
        temp: Path,
        index: int,
    ) -> tuple[Path, int, dict[str, Any]]:
        if segment.audio_url:
            local_path = resolve_local_openmaic_media_path(segment.audio_url)
            if local_path:
                path = temp / f"audio_{index}{local_path.suffix or '.wav'}"
                shutil.copyfile(local_path, path)
                duration_ms = self._audio_duration_ms(path)
                return path, duration_ms, {"source": "openmaic_local_tts", "fallback": False}
            try:
                data = await self.client.download_media(segment.audio_url)
                suffix = Path(urlparse(segment.audio_url).path).suffix or ".wav"
                path = temp / f"audio_{index}{suffix}"
                path.write_bytes(data)
                duration_ms = self._audio_duration_ms(path)
                return path, duration_ms, {"source": "openmaic_tts", "fallback": False}
            except Exception:
                pass
        result = await build_audio_provider().synthesize(segment.text, response_format="wav")
        padding = "=" * (-len(result.audio_base64) % 4)
        data = base64.b64decode(result.audio_base64 + padding)
        suffix = f".{result.format or 'wav'}"
        path = temp / f"audio_{index}{suffix}"
        path.write_bytes(data)
        duration_ms = result.duration_ms or self._audio_duration_ms(path)
        return path, max(300, duration_ms), {
            "source": result.provider,
            "model": result.model,
            "fallback": bool((result.raw or {}).get("fallback_used")) or result.provider == "mock_audio",
        }

    def _audio_duration_ms(self, path: Path) -> int:
        from moviepy import AudioFileClip

        clip = AudioFileClip(str(path))
        try:
            return max(300, int(clip.duration * 1000))
        finally:
            clip.close()

    def _render_video(
        self,
        *,
        topic: str,
        segments: list[NarrationSegment],
        audio_paths: list[Path],
        durations_ms: list[int],
        output: Path,
    ) -> None:
        from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips

        clips = []
        audio_clips = []
        scene_audio_tracks = []
        for index, (segment, audio_path, duration_ms) in enumerate(
            zip(segments, audio_paths, durations_ms, strict=True),
            start=1,
        ):
            frame_path = output.parent / f"frame_{index}.png"
            self._render_frame(topic, segment, index, len(segments), frame_path)
            audio_clip = AudioFileClip(str(audio_path))
            audio_clips.append(audio_clip)
            duration = max(audio_clip.duration, duration_ms / 1000)
            audio_track = CompositeAudioClip([audio_clip]).with_duration(duration)
            scene_audio_tracks.append(audio_track)
            clips.append(ImageClip(str(frame_path)).with_audio(audio_track).with_duration(duration))
        # All generated frames are 1280x720; chain preserves the exact cut order
        # and timing without re-compositing an identical canvas for every frame.
        final = concatenate_videoclips(clips, method="chain")
        try:
            final.write_videofile(
                str(output),
                fps=NARRATED_VIDEO_FPS,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=str(output.parent / "narration_audio.m4a"),
                preset="veryfast",
                logger=None,
            )
        finally:
            final.close()
            for clip in clips:
                clip.close()
            for track in scene_audio_tracks:
                track.close()
            for audio_clip in audio_clips:
                audio_clip.close()

    def _render_frame(
        self,
        topic: str,
        segment: NarrationSegment,
        index: int,
        total: int,
        output: Path,
    ) -> None:
        from PIL import Image, ImageDraw, ImageFont

        width, height = 1280, 720
        image = Image.new("RGB", (width, height), color=(255, 250, 244))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (48, 48, width - 48, height - 48),
            radius=36,
            fill=(255, 255, 255),
            outline=(245, 213, 170),
            width=3,
        )
        title_font = self._font(ImageFont, 46)
        body_font = self._font(ImageFont, 29)
        small_font = self._font(ImageFont, 24)
        draw.rounded_rectangle((78, 72, 274, 112), radius=20, fill=(255, 237, 207))
        draw.text((98, 80), f"第 {index} / {total} 段", fill=(152, 92, 12), font=small_font)
        draw.text((78, 142), segment.title[:28], fill=(45, 35, 24), font=title_font)
        focus = segment.visual_focus or topic
        pill_width = min(width - 156, 40 + len(focus) * 26)
        draw.rounded_rectangle((78, 212, 78 + pill_width, 252), radius=18, fill=(237, 245, 255))
        draw.text((96, 220), focus, fill=(48, 96, 148), font=small_font)

        y = 292
        for line in _wrap_text(segment.text, 29)[:4]:
            draw.text((82, y), line, fill=(72, 55, 38), font=body_font)
            y += 48

        points = segment.key_points or ("抓住规则", "联系例子", "主动回忆")
        for point_index, point in enumerate(points[:3]):
            x = 78 + point_index * 370
            draw.rounded_rectangle(
                (x, 508, x + 334, 578),
                radius=18,
                fill=(255, 248, 238),
                outline=(248, 220, 181),
                width=2,
            )
            draw.text((x + 20, 529), point, fill=(105, 68, 23), font=small_font)

        progress = index / max(total, 1)
        draw.rounded_rectangle((78, 610, width - 78, 624), radius=7, fill=(245, 233, 216))
        draw.rounded_rectangle((78, 610, 78 + int((width - 156) * progress), 624), radius=7, fill=(202, 132, 44))
        draw.rounded_rectangle((80, height - 88, width - 80, height - 46), radius=20, fill=(238, 242, 255))
        subtitle = (_wrap_text(segment.text, 28) or [""])[0][:36]
        draw.text(
            (104, height - 80),
            subtitle,
            fill=(67, 56, 202),
            font=small_font,
        )
        image.save(output)

    def _font(self, image_font, size: int):
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


def _wrap_text(text: str, width: int) -> list[str]:
    compact = " ".join(str(text or "").split())
    return [compact[index : index + width] for index in range(0, len(compact), width)] or [""]
