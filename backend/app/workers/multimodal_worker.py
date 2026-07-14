from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations.openmaic.client import OpenMAICManifest
from app.llm.multimodal_provider import build_multimodal_provider
from app.repositories.media_repository import MediaRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.classroom_video_export_service import ClassroomVideoExportService
from app.services.media_storage_service import MediaStorageService
from app.services.video_render_service import build_storyboard


@dataclass(frozen=True)
class MediaJobReference:
    """Stable job identifiers retained across rendering and database commits."""

    id: UUID
    user_id: UUID
    course_id: UUID
    resource_id: UUID | None
    agent_task_id: UUID | None
    conversation_id: UUID | None
    tool_call_id: str | None
    provider: str

    @classmethod
    def from_job(cls, job: Any) -> "MediaJobReference":
        return cls(
            id=job.id,
            user_id=job.user_id,
            course_id=job.course_id,
            resource_id=job.resource_id,
            agent_task_id=job.agent_task_id,
            conversation_id=job.conversation_id,
            tool_call_id=job.tool_call_id,
            provider=job.provider,
        )


async def run_multimodal_video_job(ctx: dict, job_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        repo = MediaRepository(db)
        job = await repo.get_job(UUID(job_id))
        if job is None:
            return {"status": "not_found"}
        reference = MediaJobReference.from_job(job)
        payload = dict(job.input_payload or {})
        if job.cancel_requested:
            await repo.update_job(job, status="cancelled", stage="cancelled", finished_at=datetime.now(UTC))
            await db.commit()
            return {"status": "cancelled"}

        try:
            await repo.update_job(job, status="running", stage="storyboard", progress=10)
            await db.commit()
            await _publish_progress(db, reference, "storyboard", 10, "正在生成视频脚本与分镜")

            topic = str(payload.get("topic") or "课程讲解")
            brief = dict(payload.get("brief") or {})
            storyboard = build_storyboard(topic, brief, int(payload.get("duration_seconds") or 90))

            await repo.update_job(job, stage="rendering", progress=45, output_payload={"storyboard": storyboard})
            await db.commit()
            await _publish_progress(db, reference, "rendering", 45, "正在渲染视频画面")

            provider = build_multimodal_provider()
            asset_path = None
            size = None
            mime = None
            render_meta: dict = {"mode": "local_storyboard"}

            if str(payload.get("visual_mode") or "") == "t2v_broll" and provider.provider_name != "mock_multimodal":
                remote = await provider.create_video_job(
                    prompt=_video_prompt(topic, brief, storyboard),
                    duration_seconds=int(payload.get("duration_seconds") or 90),
                    size="1280x720",
                )
                await repo.update_job(job, provider_job_id=remote.provider_job_id, stage="remote_video", progress=55)
                await db.commit()
                if remote.video_bytes:
                    storage = MediaStorageService()
                    asset_path, size, mime = storage.save_bytes(
                        data=remote.video_bytes, asset_type="video", suffix=".mp4"
                    )
                    render_meta = {"mode": "remote", "raw": remote.raw}

            if not asset_path:
                manifest = build_storyboard_manifest(topic, storyboard)
                asset_path, size, mime, render_meta = await ClassroomVideoExportService().export(
                    manifest=manifest,
                    topic=topic,
                )
                audio_sources = list(render_meta.get("audio_sources") or [])
                all_audio_fallback = bool(audio_sources) and all(
                    bool(source.get("fallback")) for source in audio_sources
                )
                if settings.llm_api_key and settings.llm_base_url and all_audio_fallback:
                    raise RuntimeError("MiMo 配音生成失败，已拒绝发布静音降级视频")
                render_meta = {
                    **render_meta,
                    "mode": "narrated_storyboard",
                    "audio_degraded": all_audio_fallback,
                }

            await repo.update_job(job, stage="saving", progress=85)
            await db.commit()
            await _publish_progress(db, reference, "saving", 85, "正在保存视频产物")

            asset = await repo.create_asset(
                user_id=reference.user_id,
                course_id=reference.course_id,
                resource_id=reference.resource_id,
                agent_task_id=reference.agent_task_id,
                conversation_id=reference.conversation_id,
                tool_call_id=reference.tool_call_id,
                asset_type="video" if mime == "video/mp4" else "html",
                title=f"{topic} 个性化讲解视频",
                description="由课程依据、中文讲解画面、MiMo 配音和烧录字幕合成的讲解视频。",
                storage_path=asset_path,
                mime_type=mime,
                file_size=size,
                provider="mimo_narrated_storyboard" if render_meta.get("mode") == "narrated_storyboard" else reference.provider,
                model_name=(
                    "storyboard-mimo-tts-moviepy"
                    if render_meta.get("mode") == "narrated_storyboard"
                    else "remote-video-provider"
                ),
                prompt=_video_prompt(topic, brief, storyboard),
                citations=brief.get("citations") or [],
                safety_result={
                    "passed": True,
                    "risk_level": "low",
                    "review": "grounded_narrated_storyboard",
                    "audio_degraded": bool(render_meta.get("audio_degraded")),
                },
                render_meta={**render_meta, "storyboard": storyboard},
            )
            if reference.resource_id:
                resource = await ResourceRepository(db).get_by_id(reference.resource_id)
                if resource is not None:
                    resource.content = "讲解视频已生成，可在学习资源区直接播放。"
                    resource.model_name = asset.model_name
                    await db.flush()
            artifact_refs = build_video_completion_refs(
                resource_id=str(reference.resource_id) if reference.resource_id else None,
                asset_id=str(asset.id),
                title=asset.title,
                mime_type=mime,
            )
            output_payload = {
                "asset_id": str(asset.id),
                "resource_id": str(reference.resource_id) if reference.resource_id else None,
                "artifact_refs": artifact_refs,
                "render_meta": render_meta,
            }
            await repo.mark_job_succeeded(job, asset_id=asset.id, output_payload=output_payload)
            await db.commit()
            from app.services.pet_service import PetService

            await PetService(db).safely_create_media_completion(
                user_id=reference.user_id,
                course_id=reference.course_id,
                job_id=reference.id,
                title=asset.title,
                conversation_id=reference.conversation_id,
                agent_task_id=reference.agent_task_id,
                resource_type="video",
            )
            await _publish_progress(
                db,
                reference,
                "completed",
                100,
                "视频生成完成，已放入学习资源区",
                asset_id=str(asset.id),
                resource_id=str(reference.resource_id) if reference.resource_id else None,
                artifact_refs=artifact_refs,
            )
            return {
                "status": "succeeded",
                "asset_id": str(asset.id),
                "resource_id": str(reference.resource_id) if reference.resource_id else None,
            }
        except Exception as exc:
            current_job = await repo.get_job(reference.id)
            if current_job is not None:
                await repo.mark_job_failed(current_job, str(exc))
            await db.commit()
            await _publish_progress(db, reference, "failed", 85, str(exc))
            await _notify_agent_media_job_failed(db, reference, str(exc))
            raise


async def _notify_agent_media_job_failed(db, job: MediaJobReference, message: str) -> None:
    if not job.agent_task_id:
        return
    try:
        from app.repositories.agent_conversation_repository import AgentConversationRepository
        from app.repositories.agent_task_repository import AgentTaskRepository
        from app.services.agent_queue_service import AgentEventBroker

        task_repo = AgentTaskRepository(db)
        task = await task_repo.get_by_id(job.agent_task_id)
        if task is None:
            return
        err = str(message)[:2000]
        await task_repo.update_task(
            task,
            error_message=err,
        )
        event = await AgentConversationRepository(db).add_event(
            task_id=task.id,
            conversation_id=job.conversation_id,
            event_type="failed",
            payload={
                "status": "failed",
                "error_message": err,
                "job_id": str(job.id),
                "stage": "multimodal_job_failed",
            },
        )
        await db.commit()
        await AgentEventBroker().publish(
            task.id,
            "failed",
            {"error_message": err, "sequence_no": event.sequence_no, "job_id": str(job.id)},
        )
    except Exception:
        await db.rollback()


async def _publish_progress(
    db,
    job: MediaJobReference,
    stage: str,
    progress: int,
    message: str,
    **extra,
) -> None:
    if not job.agent_task_id:
        return
    try:
        from app.repositories.agent_conversation_repository import AgentConversationRepository
        from app.services.agent_queue_service import AgentEventBroker

        repo = AgentConversationRepository(db)
        event = await repo.add_event(
            task_id=job.agent_task_id,
            conversation_id=job.conversation_id,
            event_type="multimodal_progress",
            payload={
                "job_id": str(job.id),
                "stage": stage,
                "progress": progress,
                "message": message,
                **extra,
            },
        )
        await db.commit()
        await AgentEventBroker().publish(
            job.agent_task_id,
            "multimodal_progress",
            {"sequence_no": event.sequence_no, "stage": stage, "progress": progress, "message": message, **extra},
        )
    except Exception:
        await db.rollback()
        return


def _video_prompt(topic: str, brief: dict, storyboard: list[dict]) -> str:
    return f"主题：{topic}\n课程依据：{brief.get('source_summary') or ''}\n分镜：{storyboard}"


def build_storyboard_manifest(topic: str, storyboard: list[dict]) -> OpenMAICManifest:
    scenes = []
    for index, item in enumerate(storyboard, start=1):
        title = str(item.get("title") or f"{topic} · 场景 {index}").strip()
        narration = str(item.get("narration") or item.get("body") or "").strip()
        if not narration:
            narration = f"本节讲解 {title}，请结合课程资料理解这一知识点。"
        scenes.append(
            {
                "id": f"storyboard_scene_{index}",
                "title": title,
                "duration_seconds": int(item.get("duration_seconds") or 0),
                "visual_focus": str(item.get("visual_focus") or "核心概念").strip()[:24],
                "key_points": [
                    str(point).strip()[:24]
                    for point in list(item.get("key_points") or [])[:3]
                    if str(point).strip()
                ],
                "actions": [{"type": "speech", "text": narration}],
            }
        )
    return OpenMAICManifest(
        classroom_id="fast_narrated_storyboard",
        stage={"name": topic},
        scenes=scenes,
    )


def build_video_completion_refs(
    *,
    resource_id: str | None,
    asset_id: str,
    title: str,
    mime_type: str,
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    if resource_id:
        refs.append(
            {
                "type": "resource",
                "subtype": "video",
                "id": resource_id,
                "resource_id": resource_id,
                "title": title,
            }
        )
    media_ref = {
        "type": "media_asset",
        "subtype": "video",
        "id": asset_id,
        "asset_id": asset_id,
        "title": title,
        "mime_type": mime_type,
    }
    if resource_id:
        media_ref["resource_id"] = resource_id
    refs.append(media_ref)
    return refs
