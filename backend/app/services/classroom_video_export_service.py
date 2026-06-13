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


def extract_narration_segments(
    scenes: list[dict[str, Any]],
    *,
    fallback_topic: str,
) -> list[NarrationSegment]:
    segments: list[NarrationSegment] = []
    for index, scene in enumerate(scenes, start=1):
        title = str(
            scene.get("title")
            or (scene.get("content") or {}).get("title")
            or f"{fallback_topic} · 场景 {index}"
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
                    )
                )
            continue
        segments.append(
            NarrationSegment(
                scene_id=str(scene.get("id") or f"scene_{index}"),
                title=title[:120],
                text=f"本节课堂场景：{title}。请结合画面理解这一知识点。",
                audio_url=None,
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
            durations_ms = [item[1] for item in prepared_audio]
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
        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

        clips = []
        audio_clips = []
        for index, (segment, audio_path, duration_ms) in enumerate(
            zip(segments, audio_paths, durations_ms, strict=True),
            start=1,
        ):
            frame_path = output.parent / f"frame_{index}.png"
            self._render_frame(topic, segment, index, len(segments), frame_path)
            audio_clip = AudioFileClip(str(audio_path))
            audio_clips.append(audio_clip)
            duration = max(audio_clip.duration, duration_ms / 1000)
            clips.append(ImageClip(str(frame_path)).with_duration(duration).with_audio(audio_clip))
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
        image = Image.new("RGB", (width, height), color=(242, 247, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (48, 48, width - 48, height - 48),
            radius=36,
            fill=(255, 255, 255),
            outline=(199, 210, 254),
            width=3,
        )
        title_font = self._font(ImageFont, 48)
        body_font = self._font(ImageFont, 31)
        small_font = self._font(ImageFont, 24)
        draw.text((88, 82), topic[:36], fill=(49, 46, 129), font=small_font)
        draw.text((88, 130), segment.title[:34], fill=(15, 23, 42), font=title_font)
        y = 225
        for line in _wrap_text(segment.text, 31)[:8]:
            draw.text((88, y), line, fill=(51, 65, 85), font=body_font)
            y += 48
        draw.rounded_rectangle((80, height - 108, width - 80, height - 66), radius=20, fill=(238, 242, 255))
        draw.text(
            (104, height - 100),
            f"智学工坊 · OpenMAIC 沉浸课堂 · {index}/{total}",
            fill=(67, 56, 202),
            font=small_font,
        )
        image.save(output)

    def _font(self, image_font, size: int):
        candidates = (
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )
        for candidate in candidates:
            if candidate.exists():
                return image_font.truetype(str(candidate), size)
        return image_font.load_default()


def _wrap_text(text: str, width: int) -> list[str]:
    compact = " ".join(str(text or "").split())
    return [compact[index : index + width] for index in range(0, len(compact), width)] or [""]
