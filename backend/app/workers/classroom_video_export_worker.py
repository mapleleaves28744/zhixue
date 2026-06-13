from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.integrations.openmaic.client import OpenMAICClient
from app.repositories.media_repository import MediaRepository
from app.services.classroom_video_export_service import ClassroomVideoExportService
from app.workers.multimodal_worker import _publish_progress


async def run_classroom_video_export_job(ctx: dict, job_id: str) -> dict[str, Any]:
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
        try:
            await repo.update_job(job, status="running", stage="loading_classroom", progress=10)
            await db.commit()
            await _publish_progress(db, job, "loading_classroom", 10, "正在读取沉浸课堂场景与讲解音频")

            client = OpenMAICClient()
            manifest = await client.get_manifest(str(payload["classroom_id"]))
            await repo.update_job(job, stage="exporting_video", progress=35)
            await db.commit()
            await _publish_progress(db, job, "exporting_video", 35, "正在合成配音、画面与字幕")

            path, size, mime, render_meta = await ClassroomVideoExportService(client).export(
                manifest=manifest,
                topic=topic,
            )
            citations = list(payload.get("citations") or [])
            asset = await repo.create_asset(
                user_id=job.user_id,
                course_id=job.course_id,
                resource_id=job.resource_id,
                agent_task_id=job.agent_task_id,
                conversation_id=job.conversation_id,
                tool_call_id=job.tool_call_id,
                asset_type="video",
                title=f"{topic} 个性化知识点讲解视频",
                description="由 OpenMAIC 课堂场景、讲解动作和 MiMo 配音合成的带字幕 MP4。",
                storage_path=path,
                mime_type=mime,
                file_size=size,
                provider="openmaic_mimo_export",
                model_name="openmaic-scene-mimo-tts-moviepy",
                citations=citations,
                safety_result={"passed": True, "risk_level": "low", "mode": "grounded_narrated_export"},
                render_meta={**render_meta, "classroom_asset_id": payload.get("classroom_asset_id")},
            )
            ref = {
                "type": "media_asset",
                "subtype": "narrated_classroom_video",
                "asset_id": str(asset.id),
                "title": asset.title,
                "mime_type": mime,
            }
            await repo.mark_job_succeeded(
                job,
                asset_id=asset.id,
                output_payload={"asset_id": str(asset.id), "artifact_refs": [ref], "render_meta": render_meta},
            )
            await db.commit()
            from app.services.pet_service import PetService

            await PetService(db).safely_create_media_completion(
                user_id=job.user_id,
                course_id=job.course_id,
                job_id=job.id,
                title=asset.title,
                conversation_id=job.conversation_id,
                agent_task_id=job.agent_task_id,
                resource_type="video",
            )
            await _publish_progress(
                db,
                job,
                "completed",
                100,
                "配音字幕知识点讲解视频导出完成",
                asset_id=str(asset.id),
                artifact_refs=[ref],
            )
            return {"status": "succeeded", "asset_id": str(asset.id)}
        except Exception as exc:
            await repo.mark_job_failed(job, str(exc))
            await db.commit()
            await _publish_progress(db, job, "video_export_failed", job.progress or 0, str(exc))
            raise
