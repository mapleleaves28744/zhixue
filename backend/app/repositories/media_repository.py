from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaAsset, MediaJob


class MediaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_asset(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        asset_type: str,
        title: str,
        storage_path: str,
        mime_type: str,
        resource_id: UUID | None = None,
        agent_task_id: UUID | None = None,
        conversation_id: UUID | None = None,
        tool_call_id: str | None = None,
        description: str | None = None,
        file_size: int | None = None,
        duration_ms: int | None = None,
        thumbnail_path: str | None = None,
        provider: str | None = None,
        model_name: str | None = None,
        prompt: str | None = None,
        negative_prompt: str | None = None,
        citations: list[Any] | None = None,
        safety_result: dict[str, Any] | None = None,
        render_meta: dict[str, Any] | None = None,
        status: str = "active",
    ) -> MediaAsset:
        item = MediaAsset(
            user_id=user_id,
            course_id=course_id,
            resource_id=resource_id,
            agent_task_id=agent_task_id,
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            asset_type=asset_type,
            title=title,
            description=description,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            duration_ms=duration_ms,
            thumbnail_path=thumbnail_path,
            provider=provider,
            model_name=model_name,
            prompt=prompt,
            negative_prompt=negative_prompt,
            citations=citations or [],
            safety_result=safety_result or {},
            render_meta=render_meta or {},
            status=status,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_asset_for_user(self, asset_id: UUID, user_id: UUID) -> MediaAsset | None:
        result = await self.db.execute(
            select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_asset_for_resource(self, resource_id: UUID, user_id: UUID) -> MediaAsset | None:
        result = await self.db.execute(
            select(MediaAsset)
            .where(
                MediaAsset.resource_id == resource_id,
                MediaAsset.user_id == user_id,
                MediaAsset.status == "active",
            )
            .order_by(MediaAsset.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_assets_for_resource(self, resource_id: UUID, user_id: UUID) -> list[MediaAsset]:
        result = await self.db.execute(
            select(MediaAsset)
            .where(
                MediaAsset.resource_id == resource_id,
                MediaAsset.user_id == user_id,
                MediaAsset.status == "active",
            )
            .order_by(MediaAsset.created_at.asc())
        )
        return list(result.scalars().all())

    async def update_asset(self, asset: MediaAsset, **values: Any) -> MediaAsset:
        for key, value in values.items():
            setattr(asset, key, value)
        asset.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset

    async def create_job(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        job_type: str,
        idempotency_key: str,
        provider: str,
        input_payload: dict[str, Any],
        resource_id: UUID | None = None,
        asset_id: UUID | None = None,
        agent_task_id: UUID | None = None,
        conversation_id: UUID | None = None,
        tool_call_id: str | None = None,
    ) -> MediaJob:
        existing = await self.get_job_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing
        job = MediaJob(
            user_id=user_id,
            course_id=course_id,
            resource_id=resource_id,
            asset_id=asset_id,
            agent_task_id=agent_task_id,
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            job_type=job_type,
            idempotency_key=idempotency_key,
            provider=provider,
            input_payload=input_payload,
            status="queued",
            stage="queued",
            progress=0,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def get_job_by_idempotency_key(self, key: str) -> MediaJob | None:
        result = await self.db.execute(select(MediaJob).where(MediaJob.idempotency_key == key))
        return result.scalar_one_or_none()

    async def get_job(self, job_id: UUID) -> MediaJob | None:
        result = await self.db.execute(select(MediaJob).where(MediaJob.id == job_id))
        return result.scalar_one_or_none()

    async def get_job_for_user(self, job_id: UUID, user_id: UUID) -> MediaJob | None:
        result = await self.db.execute(
            select(MediaJob).where(MediaJob.id == job_id, MediaJob.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_job_for_resource(
        self,
        resource_id: UUID,
        user_id: UUID,
    ) -> MediaJob | None:
        result = await self.db.execute(
            select(MediaJob)
            .where(
                MediaJob.resource_id == resource_id,
                MediaJob.user_id == user_id,
            )
            .order_by(MediaJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_job(self, job: MediaJob, **values: Any) -> MediaJob:
        for key, value in values.items():
            setattr(job, key, value)
        job.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def mark_job_succeeded(
        self,
        job: MediaJob,
        *,
        asset_id: UUID | None,
        output_payload: dict[str, Any],
    ) -> MediaJob:
        return await self.update_job(
            job,
            asset_id=asset_id,
            status="succeeded",
            stage="completed",
            progress=100,
            output_payload=output_payload,
            finished_at=datetime.now(UTC),
            error_message=None,
        )

    async def mark_job_failed(self, job: MediaJob, message: str) -> MediaJob:
        return await self.update_job(
            job,
            status="failed",
            stage="failed",
            error_message=message[:2000],
            finished_at=datetime.now(UTC),
        )
