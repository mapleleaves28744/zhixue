from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.llm.multimodal_provider import build_multimodal_provider
from app.repositories.media_repository import MediaRepository
from app.services.media_storage_service import MediaStorageService
from app.services.video_render_service import VideoRenderService, build_storyboard


async def run_multimodal_video_job(ctx: dict, job_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        repo = MediaRepository(db)
        job = await repo.get_job(UUID(job_id))
        if job is None:
            return {"status": "not_found"}
        if job.cancel_requested:
            await repo.update_job(job, status="cancelled", stage="cancelled", finished_at=datetime.now(UTC))
            await db.commit()
            return {"status": "cancelled"}

        try:
            await repo.update_job(job, status="running", stage="storyboard", progress=10)
            await db.commit()
            await _publish_progress(db, job, "storyboard", 10, "正在生成视频脚本与分镜")

            payload = job.input_payload or {}
            topic = str(payload.get("topic") or "课程讲解")
            brief = dict(payload.get("brief") or {})
            storyboard = build_storyboard(topic, brief, int(payload.get("duration_seconds") or 90))

            await repo.update_job(job, stage="rendering", progress=45, output_payload={"storyboard": storyboard})
            await db.commit()
            await _publish_progress(db, job, "rendering", 45, "正在渲染视频画面")

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
                video = VideoRenderService()
                asset_path, size, mime, render_meta = await video.render_storyboard_video(
                    topic=topic,
                    storyboard=storyboard,
                    duration_seconds=int(payload.get("duration_seconds") or 90),
                )

            await repo.update_job(job, stage="saving", progress=85)
            await db.commit()
            await _publish_progress(db, job, "saving", 85, "正在保存视频产物")

            asset = await repo.create_asset(
                user_id=job.user_id,
                course_id=job.course_id,
                resource_id=job.resource_id,
                agent_task_id=job.agent_task_id,
                conversation_id=job.conversation_id,
                tool_call_id=job.tool_call_id,
                asset_type="video" if mime == "video/mp4" else "html",
                title=f"{topic} 个性化讲解视频",
                description="由智学工坊生成的多模态讲解视频/分镜。",
                storage_path=asset_path,
                mime_type=mime,
                file_size=size,
                provider=job.provider,
                model_name="local-storyboard-v1",
                prompt=_video_prompt(topic, brief, storyboard),
                citations=brief.get("citations") or [],
                safety_result={"passed": True, "risk_level": "low", "review": "storyboard_based"},
                render_meta={**render_meta, "storyboard": storyboard},
            )
            await repo.mark_job_succeeded(job, asset_id=asset.id, output_payload={"asset_id": str(asset.id)})
            await db.commit()
            await _publish_progress(db, job, "completed", 100, "视频生成完成", asset_id=str(asset.id))
            return {"status": "succeeded", "asset_id": str(asset.id)}
        except Exception as exc:
            await repo.mark_job_failed(job, str(exc))
            await db.commit()
            await _publish_progress(db, job, "failed", job.progress or 0, str(exc))
            raise


async def _publish_progress(db, job, stage: str, progress: int, message: str, **extra) -> None:
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
        return


def _video_prompt(topic: str, brief: dict, storyboard: list[dict]) -> str:
    return f"主题：{topic}\n课程依据：{brief.get('source_summary') or ''}\n分镜：{storyboard}"
