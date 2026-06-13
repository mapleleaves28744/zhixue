from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from arq.connections import RedisSettings, create_pool

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations.openmaic.client import OpenMAICClient, OpenMAICError
from app.repositories.media_repository import MediaRepository
from app.services.immersive_classroom_service import CLASSROOM_MIME_TYPE, ImmersiveClassroomService
from app.services.media_storage_service import MediaStorageService
from app.workers.multimodal_worker import _publish_progress


def map_openmaic_progress(step: str, progress: int) -> tuple[str, int]:
    if step == "completed":
        return "persisting_classroom", 100
    allowed = {
        "initializing",
        "researching",
        "generating_outlines",
        "generating_scenes",
        "generating_media",
        "generating_tts",
        "persisting",
        "failed",
    }
    return (step if step in allowed else "generating_scenes", max(0, min(100, progress)))


def build_classroom_descriptor(
    *,
    classroom_id: str,
    title: str,
    scenes_count: int,
    citations: list[Any],
    personalized_reason: str | None,
) -> dict[str, Any]:
    return {
        "classroom_id": classroom_id,
        "title": title,
        "scenes_count": scenes_count,
        "citation_count": len(citations),
        "citations": citations,
        "personalized_reason": personalized_reason,
        "launch_path": None,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def run_immersive_classroom_job(ctx: dict, job_id: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        repo = MediaRepository(db)
        job = await repo.get_job(UUID(job_id))
        if job is None:
            return {"status": "not_found"}
        if job.cancel_requested:
            await repo.update_job(job, status="cancelled", stage="cancelled", finished_at=datetime.now(UTC))
            await db.commit()
            return {"status": "cancelled"}

        payload = dict(job.input_payload or {})
        topic = str(payload.get("topic") or "课程知识点")
        client = OpenMAICClient()
        try:
            await repo.update_job(job, status="running", stage="preparing_context", progress=5)
            await db.commit()
            await _publish_progress(db, job, "preparing_context", 5, "正在整理课程依据与个性化课堂要求")

            provider_job_id = job.provider_job_id
            poll_interval_seconds = max(1.0, settings.multimodal_job_poll_interval_seconds)
            if not provider_job_id:
                created = await client.create_classroom(
                    requirement=str(payload.get("requirement") or topic),
                    context_text=str(payload.get("context_text") or ""),
                    enable_images=bool(payload.get("enable_images", True)),
                    enable_video_clips=bool(payload.get("enable_video_clips", False)),
                    enable_tts=bool(payload.get("enable_tts", True)),
                )
                provider_job_id = created.job_id
                poll_interval_seconds = max(0.25, created.poll_interval_ms / 1000)
                await repo.update_job(job, provider_job_id=provider_job_id, stage=created.step, progress=8)
                await db.commit()

            deadline = time.monotonic() + settings.openmaic_job_max_wait_seconds
            provider_status = None
            last_published_stage: str | None = None
            last_published_progress: int | None = None
            while time.monotonic() < deadline:
                provider_status = await client.get_job(provider_job_id)
                stage, progress = map_openmaic_progress(provider_status.step, provider_status.progress)
                await repo.update_job(
                    job,
                    status="running",
                    stage=stage,
                    progress=progress,
                    output_payload={"openmaic_status": provider_status.raw},
                )
                await db.commit()
                progress_message = provider_status.message or f"OpenMAIC 正在执行 {stage}"
                if stage != last_published_stage or progress != last_published_progress:
                    await _publish_progress(
                        db,
                        job,
                        stage,
                        progress,
                        progress_message,
                    )
                    last_published_stage = stage
                    last_published_progress = progress
                if provider_status.status == "succeeded":
                    break
                if provider_status.status == "failed":
                    raise OpenMAICError(provider_status.error or "OpenMAIC 课堂生成失败")
                await asyncio.sleep(poll_interval_seconds)
            else:
                raise OpenMAICError("OpenMAIC 课堂生成超时")

            if provider_status is None or not provider_status.classroom_id:
                raise OpenMAICError("OpenMAIC 完成响应缺少 classroomId")

            manifest = await client.get_manifest(provider_status.classroom_id)
            scenes_count = provider_status.scenes_count or len(manifest.scenes)
            citations = list(payload.get("citations") or [])
            title = f"{topic} 个性化沉浸课堂"
            descriptor = build_classroom_descriptor(
                classroom_id=manifest.classroom_id,
                title=title,
                scenes_count=scenes_count,
                citations=citations,
                personalized_reason=str(payload.get("personalized_reason") or "") or None,
            )
            storage_path, file_size, _ = MediaStorageService().save_text(
                text=json.dumps(descriptor, ensure_ascii=False, indent=2),
                asset_type="immersive_classroom",
                suffix=".json",
            )
            asset = await repo.create_asset(
                user_id=job.user_id,
                course_id=job.course_id,
                resource_id=job.resource_id,
                agent_task_id=job.agent_task_id,
                conversation_id=job.conversation_id,
                tool_call_id=job.tool_call_id,
                asset_type="interactive_classroom",
                title=title,
                description="基于课程资料与学生画像生成的 OpenMAIC 沉浸课堂。",
                storage_path=storage_path,
                mime_type=CLASSROOM_MIME_TYPE,
                file_size=file_size,
                provider="openmaic",
                model_name="openmaic-classroom",
                prompt=str(payload.get("requirement") or "")[:4000],
                citations=citations,
                safety_result={"passed": True, "risk_level": "low", "mode": "isolated_openmaic_origin"},
                render_meta=descriptor,
            )
            ref = ImmersiveClassroomService.classroom_asset_ref(
                asset_id=str(asset.id),
                title=title,
                scenes_count=scenes_count,
                citation_count=len(citations),
                personalized_reason=str(payload.get("personalized_reason") or "") or None,
            )
            await repo.mark_job_succeeded(
                job,
                asset_id=asset.id,
                output_payload={
                    "asset_id": str(asset.id),
                    "classroom_id": manifest.classroom_id,
                    "scenes_count": scenes_count,
                    "artifact_refs": [ref],
                },
            )
            await db.commit()
            from app.services.pet_service import PetService

            await PetService(db).safely_create_media_completion(
                user_id=job.user_id,
                course_id=job.course_id,
                job_id=job.id,
                title=title,
                conversation_id=job.conversation_id,
                agent_task_id=job.agent_task_id,
            )
            await _publish_progress(
                db,
                job,
                "completed",
                100,
                "沉浸课堂生成完成",
                asset_id=str(asset.id),
                artifact_refs=[ref],
            )

            video_job_id = None
            if bool(payload.get("generate_video_export", True)):
                try:
                    video_job = await repo.create_job(
                        user_id=job.user_id,
                        course_id=job.course_id,
                        resource_id=job.resource_id,
                        job_type="classroom_video_export",
                        idempotency_key=f"classroom-video-export:{job.id}",
                        provider="openmaic_mimo_export",
                        input_payload={
                            "topic": topic,
                            "classroom_id": manifest.classroom_id,
                            "classroom_asset_id": str(asset.id),
                            "citations": citations,
                            "personalized_reason": payload.get("personalized_reason"),
                        },
                        agent_task_id=job.agent_task_id,
                        conversation_id=job.conversation_id,
                        tool_call_id=job.tool_call_id,
                    )
                    await db.commit()
                    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
                    await redis.enqueue_job("run_classroom_video_export_job", str(video_job.id))
                    await redis.close()
                    video_job_id = str(video_job.id)
                    await _publish_progress(
                        db,
                        video_job,
                        "queued",
                        0,
                        "沉浸课堂已完成，开始导出配音字幕 MP4",
                    )
                except Exception as exc:
                    await db.rollback()
                    await _publish_progress(
                        db,
                        job,
                        "video_export_queue_failed",
                        100,
                        f"沉浸课堂已完成，但 MP4 导出任务排队失败：{str(exc)[:300]}",
                    )

            return {
                "status": "succeeded",
                "asset_id": str(asset.id),
                "classroom_id": manifest.classroom_id,
                "video_job_id": video_job_id,
            }
        except Exception as exc:
            await db.rollback()
            job = await repo.get_job(UUID(job_id))
            if job is None:
                raise
            await repo.mark_job_failed(job, str(exc))
            await db.commit()
            await _publish_progress(db, job, "failed", job.progress or 0, str(exc))
            raise
