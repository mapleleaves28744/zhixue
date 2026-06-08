from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from app.core.config import settings
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
        from moviepy import ImageSequenceClip

        frames_dir = Path(settings.multimodal_storage_dir).resolve() / "_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        width, height = 1280, 720
        frame_paths: list[str] = []
        try:
            font_title = ImageFont.truetype("DejaVuSans.ttf", 48)
            font_body = ImageFont.truetype("DejaVuSans.ttf", 30)
        except Exception:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        scenes = storyboard[: max(1, min(8, len(storyboard)))] or [
            {"title": topic, "narration": f"理解 {topic} 的核心概念。"}
        ]
        for idx, scene in enumerate(scenes):
            image = Image.new("RGB", (width, height), color=(255, 248, 238))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((50, 50, width - 50, height - 50), radius=36, fill=(255, 255, 255), outline=(245, 213, 170), width=3)
            draw.text((90, 90), str(scene.get("title") or topic)[:32], fill=(45, 35, 24), font=font_title)
            text = str(scene.get("narration") or scene.get("body") or "")[:360]
            y = 180
            for line in _wrap_zh(text, width=28):
                draw.text((90, y), line, fill=(72, 55, 38), font=font_body)
                y += 45
            draw.text((90, height - 110), f"智学工坊 · Scene {idx + 1}/{len(scenes)}", fill=(120, 80, 20), font=font_body)
            frame_path = frames_dir / f"frame_{idx}.png"
            image.save(frame_path)
            frame_paths.append(str(frame_path))

        fps = 1
        repeats = max(1, duration_seconds // max(1, len(frame_paths)))
        sequence = []
        for frame in frame_paths:
            sequence.extend([frame] * repeats)
        clip = ImageSequenceClip(sequence, fps=fps)
        out_path = Path(settings.multimodal_storage_dir).resolve() / "video" / f"lesson_{abs(hash(topic))}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        clip.write_videofile(str(out_path), fps=fps, codec="libx264", audio=False, logger=None)
        data = out_path.read_bytes()
        return str(out_path), len(data), "video/mp4", {"fallback": False, "frames": len(frame_paths), "fps": fps}


def build_storyboard(topic: str, brief: dict[str, Any], duration_seconds: int) -> list[dict[str, Any]]:
    citations = brief.get("citations") or []
    scenes = [{"title": f"为什么学习 {topic}", "narration": f"本视频用课程资料和你的学习画像，快速讲清 {topic}。"}]
    for idx, item in enumerate(citations[:5], start=1):
        scenes.append({"title": f"关键依据 {idx}", "narration": str(item.get("quote") or "")[:240]})
    scenes.append({"title": "学习建议", "narration": "看完后请完成配套练习，并把不确定的步骤标记出来。"})
    _ = duration_seconds
    return scenes


def _wrap_zh(text: str, width: int) -> list[str]:
    return [text[i : i + width] for i in range(0, len(text), width)] or [""]
