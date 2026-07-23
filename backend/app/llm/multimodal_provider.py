from __future__ import annotations

import base64
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings


@dataclass
class ImageGenerationResult:
    image_bytes: bytes
    mime_type: str = "image/png"
    provider: str = "mock"
    model: str = "mock-image"
    prompt: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoJobResult:
    provider_job_id: str | None = None
    video_url: str | None = None
    video_bytes: bytes | None = None
    status: str = "succeeded"
    provider: str = "mock"
    model: str = "mock-video"
    raw: dict[str, Any] = field(default_factory=dict)


class BaseMultimodalProvider(ABC):
    provider_name = "base"

    @abstractmethod
    async def generate_image(self, *, prompt: str, size: str, style: str | None = None) -> ImageGenerationResult:
        ...

    @abstractmethod
    async def create_video_job(self, *, prompt: str, duration_seconds: int, size: str = "1280x720") -> VideoJobResult:
        ...

    @abstractmethod
    async def get_video_job(self, provider_job_id: str) -> VideoJobResult:
        ...


class MockMultimodalProvider(BaseMultimodalProvider):
    provider_name = "mock_multimodal"

    async def generate_image(self, *, prompt: str, size: str, style: str | None = None) -> ImageGenerationResult:
        from PIL import Image, ImageDraw, ImageFont

        width, height = _parse_size(size)
        image = Image.new("RGB", (width, height), color=(248, 244, 235))
        draw = ImageDraw.Draw(image)
        text = f"智学工坊 Mock 教学插图\n\n{prompt[:240]}"
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        draw.multiline_text((48, 48), text, fill=(45, 39, 32), font=font, spacing=12)
        out = Path(settings.multimodal_storage_dir) / "_tmp_mock_image.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out, format="PNG")
        return ImageGenerationResult(
            image_bytes=out.read_bytes(),
            provider=self.provider_name,
            model="mock-image",
            prompt=prompt,
            raw={"mock": True, "size": size, "style": style},
        )

    async def create_video_job(self, *, prompt: str, duration_seconds: int, size: str = "1280x720") -> VideoJobResult:
        job_id = hashlib.sha1(f"{prompt}:{duration_seconds}:{size}".encode("utf-8")).hexdigest()[:24]
        return VideoJobResult(
            provider_job_id=f"mock_{job_id}",
            status="succeeded",
            provider=self.provider_name,
            model="mock-video",
            raw={"mock": True, "prompt": prompt[:500]},
        )

    async def get_video_job(self, provider_job_id: str) -> VideoJobResult:
        return VideoJobResult(
            provider_job_id=provider_job_id,
            status="succeeded",
            provider=self.provider_name,
            model="mock-video",
        )


class AgnesSapiensMultimodalProvider(BaseMultimodalProvider):
    provider_name = "agnes_sapiens"

    async def generate_image(self, *, prompt: str, size: str, style: str | None = None) -> ImageGenerationResult:
        full_prompt = prompt
        if style:
            full_prompt = f"{prompt}\n\nVisual style: {style}"
        payload: dict[str, Any] = {
            "model": settings.agnes_image_model,
            "prompt": full_prompt,
            "size": size,
            "extra_body": {"response_format": "url"},
        }
        payload = {k: v for k, v in payload.items() if v not in (None, "")}
        data = await self._post_json(settings.agnes_image_path, payload)

        b64_value = _json_path(data, settings.agnes_image_b64_json_path)
        url_value = _json_path(data, settings.agnes_image_url_json_path)
        if isinstance(b64_value, str) and b64_value.strip():
            return ImageGenerationResult(
                image_bytes=base64.b64decode(_strip_data_url_prefix(b64_value)),
                provider=self.provider_name,
                model=settings.agnes_image_model,
                prompt=prompt,
                raw=data,
            )
        if isinstance(url_value, str) and url_value.strip():
            async with httpx.AsyncClient(timeout=settings.agnes_timeout_seconds) as client:
                resp = await client.get(url_value)
                resp.raise_for_status()
                return ImageGenerationResult(
                    image_bytes=resp.content,
                    mime_type=resp.headers.get("content-type", "image/png").split(";")[0],
                    provider=self.provider_name,
                    model=settings.agnes_image_model,
                    prompt=prompt,
                    raw=data,
                )
        raise RuntimeError(f"Agnes image response missing image url/base64: {json.dumps(data, ensure_ascii=False)[:1000]}")

    async def create_video_job(self, *, prompt: str, duration_seconds: int, size: str = "1280x720") -> VideoJobResult:
        width, height = _parse_size(size)
        frame_rate = 24
        num_frames = _duration_to_num_frames(duration_seconds, frame_rate)
        payload = {
            "model": settings.agnes_video_model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_frames": num_frames,
            "frame_rate": frame_rate,
        }
        payload = {k: v for k, v in payload.items() if v not in (None, "")}
        data = await self._post_json(settings.agnes_video_create_path, payload)
        job_id = _json_path(data, settings.agnes_video_job_id_json_path)
        video_url = _json_path(data, settings.agnes_video_url_json_path)
        status = str(_json_path(data, settings.agnes_video_status_json_path) or "queued")
        return VideoJobResult(
            provider_job_id=str(job_id) if job_id else None,
            video_url=str(video_url) if video_url else None,
            status=_normalize_status(status),
            provider=self.provider_name,
            model=settings.agnes_video_model,
            raw=data,
        )

    async def get_video_job(self, provider_job_id: str) -> VideoJobResult:
        path = settings.agnes_video_status_path.replace("{job_id}", provider_job_id)
        data = await self._get_json(path)
        video_url = _json_path(data, settings.agnes_video_url_json_path)
        status = str(_json_path(data, settings.agnes_video_status_json_path) or "running")
        video_bytes = None
        if video_url and _normalize_status(status) == "succeeded":
            async with httpx.AsyncClient(timeout=settings.agnes_timeout_seconds) as client:
                resp = await client.get(str(video_url))
                resp.raise_for_status()
                video_bytes = resp.content
        return VideoJobResult(
            provider_job_id=provider_job_id,
            video_url=str(video_url) if video_url else None,
            video_bytes=video_bytes,
            status=_normalize_status(status),
            provider=self.provider_name,
            model=settings.agnes_video_model,
            raw=data,
        )

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=settings.agnes_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.agnes_base_url.rstrip('/')}/{path.lstrip('/')}",
                headers=self._headers(),
                json=payload,
            )
            if resp.is_error:
                detail = resp.text[:2000]
                raise RuntimeError(
                    f"Agnes API POST {path} failed ({resp.status_code}): {detail}"
                )
            return resp.json()

    async def _get_json(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=settings.agnes_timeout_seconds) as client:
            resp = await client.get(
                f"{settings.agnes_base_url.rstrip('/')}/{path.lstrip('/')}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def _headers(self) -> dict[str, str]:
        value = settings.agnes_api_key
        if settings.agnes_auth_scheme:
            value = f"{settings.agnes_auth_scheme} {value}"
        return {
            settings.agnes_auth_header: value,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


class CloudBaseImageProvider(BaseMultimodalProvider):
    """CloudBase 教育智能体的 OpenAI 兼容文生图适配器。"""

    provider_name = "cloudbase_image"

    async def generate_image(self, *, prompt: str, size: str, style: str | None = None) -> ImageGenerationResult:
        full_prompt = f"{prompt}\n\n视觉风格：{style}" if style else prompt
        payload = {
            "model": settings.cloudbase_image_model,
            "prompt": full_prompt,
            "size": self._normalize_size(size),
            "revise": {"value": True},
            "enable_thinking": {"value": False},
        }
        endpoint = f"{settings.cloudbase_image_base_url.rstrip('/')}/images/generations"
        async with httpx.AsyncClient(timeout=settings.cloudbase_image_timeout_seconds) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {settings.cloudbase_image_api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if response.is_error:
                raise RuntimeError(f"CloudBase image API failed ({response.status_code}): {response.text[:1000]}")
            data = response.json()

            b64_value = _json_path(data, "data.0.b64_json")
            if isinstance(b64_value, str) and b64_value.strip():
                return ImageGenerationResult(
                    image_bytes=base64.b64decode(_strip_data_url_prefix(b64_value)),
                    provider=self.provider_name,
                    model=settings.cloudbase_image_model,
                    prompt=prompt,
                    raw=data,
                )

            url_value = _json_path(data, "data.0.url")
            if isinstance(url_value, str) and url_value.strip():
                image_response = await client.get(url_value)
                image_response.raise_for_status()
                return ImageGenerationResult(
                    image_bytes=image_response.content,
                    mime_type=image_response.headers.get("content-type", "image/png").split(";", 1)[0],
                    provider=self.provider_name,
                    model=settings.cloudbase_image_model,
                    prompt=prompt,
                    raw=data,
                )
        raise RuntimeError("CloudBase image response missing image url/base64")

    async def create_video_job(self, *, prompt: str, duration_seconds: int, size: str = "1280x720") -> VideoJobResult:
        raise RuntimeError("当前 CloudBase Provider 仅用于生图，视频仍由本地课堂渲染器生成。")

    async def get_video_job(self, provider_job_id: str) -> VideoJobResult:
        raise RuntimeError("当前 CloudBase Provider 不支持远程视频任务。")

    @staticmethod
    def _normalize_size(size: str) -> str:
        width, height = _parse_size(size)
        if width > height:
            return "1280x720"
        if height > width:
            return "720x1280"
        return "1024x1024"


class QwenImageProvider(BaseMultimodalProvider):
    """阿里云百炼 Qwen Image 同步文生图适配器。"""

    provider_name = "qwen_image"
    prefers_natural_prompt = True

    async def generate_image(self, *, prompt: str, size: str, style: str | None = None) -> ImageGenerationResult:
        # Qwen 的官方 prompt_extend 负责扩写；这里有意不再拼接 style 或课程资料摘要。
        # 这样用户输入的自然语言需求可以原样进入模型，避免过度约束导致教学图失真。
        payload = {
            "model": settings.qwen_image_model,
            "input": {
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]},
                ],
            },
            "parameters": {
                "prompt_extend": settings.qwen_image_prompt_extend,
                "watermark": False,
                "size": self._normalize_size(size),
            },
        }
        async with httpx.AsyncClient(timeout=settings.qwen_image_timeout_seconds) as client:
            response = await client.post(
                settings.qwen_image_base_url,
                headers={
                    "Authorization": f"Bearer {settings.qwen_image_api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )
            if response.is_error:
                raise RuntimeError(f"Qwen image API failed ({response.status_code}): {response.text[:1000]}")
            data = response.json()
            error_code = data.get("code") if isinstance(data, dict) else None
            if error_code:
                message = data.get("message", "unknown error")
                raise RuntimeError(f"Qwen image API failed ({error_code}): {message}")

            url_value = _json_path(data, "output.choices.0.message.content.0.image")
            if isinstance(url_value, str) and url_value.strip():
                image_response = await client.get(url_value)
                image_response.raise_for_status()
                return ImageGenerationResult(
                    image_bytes=image_response.content,
                    mime_type=image_response.headers.get("content-type", "image/png").split(";", 1)[0],
                    provider=self.provider_name,
                    model=settings.qwen_image_model,
                    prompt=prompt,
                    raw=data,
                )
        raise RuntimeError("Qwen image response missing image url")

    async def create_video_job(self, *, prompt: str, duration_seconds: int, size: str = "1280x720") -> VideoJobResult:
        raise RuntimeError("当前 Qwen Provider 仅用于生图，视频仍由本地课堂渲染器生成。")

    async def get_video_job(self, provider_job_id: str) -> VideoJobResult:
        raise RuntimeError("当前 Qwen Provider 不支持远程视频任务。")

    @staticmethod
    def _normalize_size(size: str) -> str:
        width, height = _parse_size(size)
        return f"{width}*{height}"


def build_multimodal_provider() -> BaseMultimodalProvider:
    provider = settings.multimodal_provider.lower().replace("-", "_")
    if provider in {"qwen", "qwen_image", "dashscope", "alibaba"}:
        if not settings.qwen_image_api_key or not settings.qwen_image_base_url:
            return MockMultimodalProvider()
        return QwenImageProvider()
    if provider in {"cloudbase", "cloudbase_image", "tcloudbase"}:
        if not settings.cloudbase_image_api_key or not settings.cloudbase_image_base_url:
            return MockMultimodalProvider()
        return CloudBaseImageProvider()
    if provider in {"agnes", "sapiens", "agnes_sapiens"}:
        if not settings.agnes_api_key:
            return MockMultimodalProvider()
        return AgnesSapiensMultimodalProvider()
    return MockMultimodalProvider()


def uses_real_image_generation(provider: BaseMultimodalProvider | None = None) -> bool:
    """是否配置了可用的文生图 Provider（非 Mock 占位）。"""
    provider = provider or build_multimodal_provider()
    return not isinstance(provider, MockMultimodalProvider)


_AGNES_ALLOWED_NUM_FRAMES = (81, 121, 161, 241, 441)


def _parse_size(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x", 1)
        return max(320, int(w)), max(240, int(h))
    except Exception:
        return 1280, 720


def _duration_to_num_frames(duration_seconds: int, frame_rate: int = 24) -> int:
    target = max(1, duration_seconds) * frame_rate
    chosen = _AGNES_ALLOWED_NUM_FRAMES[-1]
    for frames in _AGNES_ALLOWED_NUM_FRAMES:
        if frames >= target:
            return frames
    return chosen


def _strip_data_url_prefix(value: str) -> str:
    if value.startswith("data:") and "," in value:
        return value.split(",", 1)[1]
    return value


def _json_path(data: Any, path: str) -> Any:
    current = data
    for part in (path or "").split("."):
        if part == "":
            continue
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except Exception:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _normalize_status(value: str) -> str:
    lowered = value.lower()
    if lowered in {"success", "succeeded", "completed", "complete", "done", "finished"}:
        return "succeeded"
    if lowered in {"fail", "failed", "error"}:
        return "failed"
    if lowered in {"queued", "pending", "created"}:
        return "queued"
    return "running"
