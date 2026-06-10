from __future__ import annotations

import base64
import re
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.audio_provider import build_audio_provider
from app.models.resource import GeneratedResource
from app.models.user import User
from app.repositories.media_repository import MediaRepository
from app.services.media_storage_service import MediaStorageService
from app.utils.mermaid_util import is_mermaid_code, kroki_encode, repair_mermaid_content

VISUAL_RESOURCE_TYPES = frozenset({"mindmap", "diagram"})
AUDIO_RESOURCE_TYPES = frozenset({"explanation"})


class ResourceMediaService:
    """为文本类资源附加可预览的多模态产物（图片 / 语音）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.media = MediaRepository(db)
        self.storage = MediaStorageService()

    async def enrich_after_generate(
        self,
        *,
        resource: GeneratedResource,
        current_user: User,
        resource_type: str,
        requirement: str | None = None,
    ) -> GeneratedResource:
        existing = await self.media.get_asset_for_resource(resource.id, current_user.id)
        if existing is not None:
            return resource

        if resource_type in VISUAL_RESOURCE_TYPES:
            await self._attach_mermaid_image(resource=resource, current_user=current_user)
        elif resource_type in AUDIO_RESOURCE_TYPES or self._wants_audio(requirement):
            await self._attach_explanation_audio(
                resource=resource,
                current_user=current_user,
                requirement=requirement,
            )
        return resource

    async def _attach_mermaid_image(
        self,
        *,
        resource: GeneratedResource,
        current_user: User,
    ) -> None:
        mermaid_code = repair_mermaid_content(resource.content, root_label=resource.title[:20])
        if not is_mermaid_code(mermaid_code):
            return
        resource.content = mermaid_code

        image_bytes, mime_type, render_mode = await self._render_mermaid(mermaid_code)
        if not image_bytes:
            return

        suffix = ".png" if mime_type == "image/png" else ".svg"
        path, file_size, mime = self.storage.save_bytes(
            data=image_bytes,
            asset_type="image",
            suffix=suffix,
        )
        await self.media.create_asset(
            user_id=current_user.id,
            course_id=resource.course_id,
            resource_id=resource.id,
            asset_type="image",
            title=resource.title,
            description="思维导图/图解可视化预览",
            storage_path=path,
            mime_type=mime,
            file_size=file_size,
            provider="kroki" if render_mode == "kroki_png" else "mermaid_svg",
            model_name="mermaid-render",
            render_meta={"mermaid_code": mermaid_code, "render_mode": render_mode},
        )
        if resource.content != mermaid_code:
            resource.content = mermaid_code

    async def _attach_explanation_audio(
        self,
        *,
        resource: GeneratedResource,
        current_user: User,
        requirement: str | None,
    ) -> None:
        speech_text = self._speech_text_from_markdown(resource.content)
        if len(speech_text) < 20:
            return

        provider = build_audio_provider()
        audio_format = "mp3" if provider.provider_name != "mock_audio" else "wav"
        result = await provider.synthesize(speech_text[:2800], response_format=audio_format)
        if not result.audio_base64:
            return
        audio_bytes = base64.b64decode(result.audio_base64)
        suffix = ".mp3" if audio_format == "mp3" else ".wav"
        mime = "audio/mpeg" if suffix == ".mp3" else "audio/wav"

        path, file_size, mime = self.storage.save_bytes(
            data=audio_bytes,
            asset_type="audio",
            suffix=suffix,
        )
        await self.media.create_asset(
            user_id=current_user.id,
            course_id=resource.course_id,
            resource_id=resource.id,
            asset_type="audio",
            title=f"{resource.title} · 语音讲解",
            description="基于讲解正文自动合成的语音朗读",
            storage_path=path,
            mime_type=mime,
            file_size=file_size,
            provider=result.provider,
            model_name=result.model,
            render_meta={
                "fallback_used": result.provider == "mock_audio",
                "requirement": requirement,
                "speech_preview": speech_text[:240],
            },
        )

    async def _render_mermaid(self, mermaid_code: str) -> tuple[bytes | None, str, str]:
        encoded = kroki_encode(mermaid_code)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                png_resp = await client.get(f"https://kroki.io/mermaid/png/{encoded}")
                if png_resp.status_code == 200 and png_resp.content:
                    return png_resp.content, "image/png", "kroki_png"
                svg_resp = await client.get(f"https://kroki.io/mermaid/svg/{encoded}")
                if svg_resp.status_code == 200 and svg_resp.content:
                    return svg_resp.content, "image/svg+xml", "kroki_svg"
        except Exception:
            pass
        return None, "", "failed"

    @staticmethod
    def _wants_audio(requirement: str | None) -> bool:
        text = str(requirement or "")
        return any(key in text for key in ("语音", "朗读", "播报", "audio", "TTS"))

    @staticmethod
    def _speech_text_from_markdown(content: str) -> str:
        text = str(content or "")
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"[*_`>#-]", "", text)
        text = re.sub(r"\n{2,}", "。", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
