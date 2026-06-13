from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.learning_record import LearningRecord
from app.models.learning_session import LearningSession
from app.models.student_knowledge_mastery import StudentKnowledgeMastery
from app.schemas.learning_analytics import LearningAnalyticsSummary, SessionHeartbeatRequest


class LearningAnalyticsService:
    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db

    @staticmethod
    def calculate_active_delta(previous: datetime, now: datetime, *, active: bool) -> int:
        if not active:
            return 0
        return max(0, min(60, int((now - previous).total_seconds())))

    async def heartbeat(self, user_id: UUID, payload: SessionHeartbeatRequest) -> LearningSession:
        assert self.db is not None
        now = datetime.now(UTC)
        session = await self.db.get(LearningSession, payload.session_id) if payload.session_id else None
        if session is None or session.user_id != user_id or session.ended_at is not None:
            session = LearningSession(user_id=user_id, course_id=payload.course_id, page=payload.page, started_at=now, last_heartbeat_at=now)
            self.db.add(session)
        else:
            previous = session.last_heartbeat_at
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=UTC)
            session.active_seconds += self.calculate_active_delta(previous, now, active=payload.active)
            session.last_heartbeat_at = now
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def end(self, user_id: UUID, session_id: UUID) -> LearningSession:
        assert self.db is not None
        session = await self.db.get(LearningSession, session_id)
        if session is None or session.user_id != user_id:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="学习会话不存在",
                status_code=404,
            )
        session.ended_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def summary(self, user_id: UUID, course_id: UUID | None, period: str) -> LearningAnalyticsSummary:
        assert self.db is not None
        normalized_period = period.strip().lower()
        if normalized_period not in {"week", "month"}:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="period 仅支持 week 或 month",
                status_code=400,
            )
        now = datetime.now(UTC)
        start = now - timedelta(days=7 if normalized_period == "week" else 30)
        session_filter = [LearningSession.user_id == user_id, LearningSession.started_at >= start]
        record_filter = [LearningRecord.user_id == user_id, LearningRecord.created_at >= start]
        mastery_filter = [StudentKnowledgeMastery.user_id == user_id]
        if course_id is not None:
            session_filter.append(LearningSession.course_id == course_id)
            record_filter.append(LearningRecord.course_id == course_id)
            mastery_filter.append(StudentKnowledgeMastery.course_id == course_id)

        total = int((await self.db.execute(select(func.coalesce(func.sum(LearningSession.active_seconds), 0)).where(*session_filter))).scalar() or 0)
        rows = (await self.db.execute(select(LearningSession).where(*session_filter))).scalars().all()
        daily_map: dict[str, int] = {}
        for row in rows:
            key = row.started_at.date().isoformat()
            daily_map[key] = daily_map.get(key, 0) + row.active_seconds
        mastery = (await self.db.execute(select(func.avg(StudentKnowledgeMastery.mastery_score)).where(*mastery_filter))).scalar()
        record_rows = (await self.db.execute(select(LearningRecord.event_type, func.count()).where(*record_filter).group_by(LearningRecord.event_type))).all()
        raw_counts = {str(key): int(count) for key, count in record_rows}
        return LearningAnalyticsSummary(
            period=normalized_period,
            active_seconds=total,
            active_hours=round(total / 3600, 1),
            mastery=round(float(mastery) * 100, 1) if mastery is not None else None,
            daily=[{"date": key, "active_seconds": value} for key, value in sorted(daily_map.items())],
            counts={
                "qa": sum(v for k, v in raw_counts.items() if "ask" in k or "chat" in k),
                "practice": sum(v for k, v in raw_counts.items() if "practice" in k or "quiz" in k),
                "knowledge": sum(v for k, v in raw_counts.items() if "wiki" in k or "knowledge" in k),
            },
        )
