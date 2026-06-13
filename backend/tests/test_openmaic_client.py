from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest

from app.integrations.openmaic.client import OpenMAICClient


@pytest.mark.asyncio
async def test_openmaic_client_creates_and_reads_classroom_job() -> None:
    seen_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers.get("x-openmaic-internal-token", ""))
        if request.url.path == "/api/generate-classroom":
            return httpx.Response(
                202,
                json={
                    "success": True,
                    "jobId": "job_123",
                    "status": "queued",
                    "step": "queued",
                    "pollIntervalMs": 250,
                },
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "jobId": "job_123",
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "result": {"classroomId": "room_123", "url": "http://openmaic/classroom/room_123"},
            },
        )

    client = OpenMAICClient(
        base_url="http://openmaic",
        internal_token="internal-secret",
        signing_secret="signing-secret",
        transport=httpx.MockTransport(handler),
    )

    created = await client.create_classroom(
        requirement="讲解 BFS",
        context_text="课程依据",
        enable_images=True,
        enable_video_clips=False,
        enable_tts=True,
    )
    status = await client.get_job(created.job_id)

    assert created.job_id == "job_123"
    assert status.status == "succeeded"
    assert status.classroom_id == "room_123"
    assert seen_headers == ["internal-secret", "internal-secret"]


@pytest.mark.asyncio
async def test_openmaic_client_reads_manifest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/classrooms/room_123/manifest"
        return httpx.Response(
            200,
            json={
                "success": True,
                "id": "room_123",
                "stage": {"id": "room_123", "name": "BFS"},
                "scenes": [{"id": "scene_1", "type": "slide", "actions": []}],
                "createdAt": "2026-06-13T00:00:00Z",
            },
        )

    client = OpenMAICClient(
        base_url="http://openmaic",
        internal_token="internal-secret",
        signing_secret="signing-secret",
        transport=httpx.MockTransport(handler),
    )

    manifest = await client.get_manifest("room_123")

    assert manifest.classroom_id == "room_123"
    assert manifest.stage["name"] == "BFS"
    assert len(manifest.scenes) == 1


def test_openmaic_client_builds_compatible_playback_signature() -> None:
    client = OpenMAICClient(
        base_url="http://internal-openmaic",
        public_base_url="https://classroom.example",
        internal_token="internal-secret",
        signing_secret="signing-secret",
    )

    url = client.build_signed_playback_url("room_123", expires_at_seconds=2_000_000_000)
    expiry = "2000000000"
    signature = hmac.new(b"signing-secret", f"room_123:{expiry}".encode(), hashlib.sha256).hexdigest()

    assert url == f"https://classroom.example/classroom/room_123?zhixue_token=room_123.{expiry}.{signature}"
