from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings


class OpenMAICError(RuntimeError):
    """OpenMAIC integration request failed."""


@dataclass(frozen=True)
class OpenMAICJobCreated:
    job_id: str
    status: str
    step: str
    poll_interval_ms: int = 5000


@dataclass(frozen=True)
class OpenMAICJobStatus:
    job_id: str
    status: str
    step: str
    progress: int
    message: str = ""
    done: bool = False
    classroom_id: str | None = None
    classroom_url: str | None = None
    scenes_count: int | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenMAICManifest:
    classroom_id: str
    stage: dict[str, Any]
    scenes: list[dict[str, Any]]
    created_at: str | None = None


class OpenMAICClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        public_base_url: str | None = None,
        internal_token: str | None = None,
        signing_secret: str | None = None,
        timeout_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.openmaic_base_url).rstrip("/")
        self.public_base_url = (public_base_url or settings.openmaic_public_base_url or self.base_url).rstrip("/")
        self.internal_token = internal_token if internal_token is not None else settings.openmaic_internal_token
        self.signing_secret = signing_secret if signing_secret is not None else settings.openmaic_signing_secret
        self.timeout_seconds = timeout_seconds or settings.openmaic_request_timeout_seconds
        self.transport = transport

    async def create_classroom(
        self,
        *,
        requirement: str,
        context_text: str,
        enable_images: bool,
        enable_video_clips: bool,
        enable_tts: bool,
    ) -> OpenMAICJobCreated:
        body = await self._request(
            "POST",
            "/api/generate-classroom",
            json={
                "requirement": requirement,
                "pdfContent": {"text": context_text, "images": []},
                "enableImageGeneration": enable_images,
                "enableVideoGeneration": enable_video_clips,
                "enableTTS": enable_tts,
                "agentMode": "generate",
            },
        )
        return OpenMAICJobCreated(
            job_id=str(body["jobId"]),
            status=str(body.get("status") or "queued"),
            step=str(body.get("step") or "queued"),
            poll_interval_ms=int(body.get("pollIntervalMs") or 5000),
        )

    async def get_job(self, job_id: str) -> OpenMAICJobStatus:
        body = await self._request("GET", f"/api/generate-classroom/{quote(job_id, safe='')}")
        result = body.get("result") if isinstance(body.get("result"), dict) else {}
        return OpenMAICJobStatus(
            job_id=str(body.get("jobId") or job_id),
            status=str(body.get("status") or "unknown"),
            step=str(body.get("step") or "unknown"),
            progress=int(body.get("progress") or 0),
            message=str(body.get("message") or ""),
            done=bool(body.get("done")),
            classroom_id=str(result.get("classroomId")) if result.get("classroomId") else None,
            classroom_url=str(result.get("url")) if result.get("url") else None,
            scenes_count=int(result.get("scenesCount")) if result.get("scenesCount") is not None else None,
            error=str(body.get("error")) if body.get("error") else None,
            raw=body,
        )

    async def get_manifest(self, classroom_id: str) -> OpenMAICManifest:
        body = await self._request("GET", f"/api/classrooms/{quote(classroom_id, safe='')}/manifest")
        return OpenMAICManifest(
            classroom_id=str(body.get("id") or classroom_id),
            stage=dict(body.get("stage") or {}),
            scenes=list(body.get("scenes") or []),
            created_at=str(body.get("createdAt")) if body.get("createdAt") else None,
        )

    async def health_check(self) -> dict[str, Any]:
        return await self._request("GET", "/api/health", include_internal_token=False)

    async def download_media(self, url: str, *, max_bytes: int = 100 * 1024 * 1024) -> bytes:
        resolved = urljoin(f"{self.base_url}/", url)
        expected = urlparse(self.base_url)
        actual = urlparse(resolved)
        if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
            raise OpenMAICError("拒绝下载非 OpenMAIC 来源的媒体")
        if not self.internal_token:
            raise OpenMAICError("OPENMAIC_INTERNAL_TOKEN 未配置")
        try:
            async with httpx.AsyncClient(timeout=max(self.timeout_seconds, 120), transport=self.transport) as client:
                response = await client.get(
                    resolved,
                    headers={"x-openmaic-internal-token": self.internal_token},
                )
                response.raise_for_status()
                data = response.content
        except httpx.HTTPError as exc:
            raise OpenMAICError(f"OpenMAIC 媒体下载失败：{exc}") from exc
        if len(data) > max_bytes:
            raise OpenMAICError("OpenMAIC 媒体超过大小限制")
        return data

    def build_signed_playback_url(self, classroom_id: str, *, expires_at_seconds: int) -> str:
        if not self.signing_secret:
            raise OpenMAICError("OPENMAIC_SIGNING_SECRET 未配置")
        expiry = str(int(expires_at_seconds))
        signed_value = f"{classroom_id}:{expiry}"
        signature = hmac.new(
            self.signing_secret.encode("utf-8"),
            signed_value.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        token = f"{classroom_id}.{expiry}.{signature}"
        return f"{self.public_base_url}/classroom/{quote(classroom_id, safe='')}?zhixue_token={token}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        include_internal_token: bool = True,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if include_internal_token:
            if not self.internal_token:
                raise OpenMAICError("OPENMAIC_INTERNAL_TOKEN 未配置")
            headers["x-openmaic-internal-token"] = self.internal_token
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.request(method, path, headers=headers, json=json)
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OpenMAICError(f"OpenMAIC 请求失败：{exc}") from exc
        if response.is_error or body.get("success") is False:
            detail = body.get("details") or body.get("error") or response.reason_phrase
            raise OpenMAICError(f"OpenMAIC 返回错误：{detail}")
        return dict(body)
