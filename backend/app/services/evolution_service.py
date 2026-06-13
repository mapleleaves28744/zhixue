from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.diagnosis import DiagnosisReport
from app.models.evolution import EvolutionEvent, EvolutionStrategy
from app.schemas.evolution import EventRead, StrategyRead


class EvolutionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def analyze(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        focus: str,
        trigger_type: str = "manual",
    ) -> tuple[EvolutionEvent, list[EvolutionStrategy]]:
        from app.agents.context import AgentContext
        from app.agents.evolution_agent import EvolutionAgent
        from app.agents.review_agent import ReviewAgent
        from app.services.learning_record_service import LearningRecordService
        from app.services.memory_service import MemoryService
        from app.services.profile_service import ProfileService

        profile_svc = ProfileService(self.db)
        memory_svc = MemoryService(self.db)
        record_svc = LearningRecordService(self.db)

        profile = await profile_svc.get_profile(user_id)
        memories = await memory_svc.list_memories(user_id, course_id)
        records = await record_svc.list_records(user_id, course_id, limit=20)

        evidence_parts = [f"分析焦点：{focus}"]
        if profile.profile_summary:
            evidence_parts.append(f"画像摘要：{profile.profile_summary}")
        if profile.weak_points:
            evidence_parts.append(f"薄弱点：{profile.weak_points}")
        if memories:
            memory_texts = [f"- {m.content} (类型:{m.memory_type}, 置信度:{m.confidence})" for m in memories[:5]]
            evidence_parts.append("长期记忆：\n" + "\n".join(memory_texts))
        if records:
            record_texts = [f"- {r.event_type}: {r.event_payload}" for r in records[:5]]
            evidence_parts.append("近期学习行为：\n" + "\n".join(record_texts))

        evidence_text = "\n\n".join(evidence_parts)

        event = EvolutionEvent(
            user_id=user_id,
            course_id=course_id,
            trigger_type=trigger_type,
            focus=focus,
            input_snapshot={"evidence_length": len(evidence_text)},
            status="pending",
        )
        self.db.add(event)
        await self.db.flush()

        evolution_agent = EvolutionAgent(self.db)
        agent_context = AgentContext(
            user_id=user_id,
            course_id=course_id,
            task_type="evolution.analyze",
            params={"evidence": evidence_text},
        )
        agent_result = await evolution_agent.run(agent_context)

        if not agent_result.success:
            event.status = "failed"
            event.error_message = agent_result.message
            await self.db.commit()
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail=agent_result.message,
                status_code=500,
            )

        raw_strategies = agent_result.data.get("strategies", [])

        review_agent = ReviewAgent(self.db)
        review_context = AgentContext(
            user_id=user_id,
            course_id=course_id,
            task_type="evolution.review",
            params={"content": str(raw_strategies[:3000])},
        )
        review_result = await review_agent.run(review_context)
        reviewed_risk = "medium"
        if review_result.success:
            reviewed_risk = review_result.data.get("risk_level", "medium")

        current_version = await self._get_latest_version(user_id, course_id)

        strategies: list[EvolutionStrategy] = []
        for i, raw in enumerate(raw_strategies):
            from app.services.strategy_materialization_service import StrategyMaterializationService

            strategy_type = StrategyMaterializationService.normalize_strategy_type(raw.get("strategy_type", "recommendation"))
            risk_level = raw.get("risk_level", reviewed_risk)
            if risk_level not in ("low", "medium", "high"):
                risk_level = "medium"

            existing_active = await self._find_active_strategy(
                user_id, course_id, strategy_type,
            )

            strategy = EvolutionStrategy(
                user_id=user_id,
                course_id=course_id,
                strategy_type=strategy_type,
                before_value=raw.get("before_value", existing_active.after_value if existing_active else {}),
                after_value=raw.get("after_value", {}),
                description=raw.get("description", ""),
                status="draft",
                risk_level=risk_level,
                evidence=raw.get("evidence", [focus]),
                previous_strategy_id=existing_active.id if existing_active else None,
                version_no=current_version + i + 1,
            )
            self.db.add(strategy)
            strategies.append(strategy)

        event.status = "completed"
        event.strategies_generated = len(strategies)
        await self.db.commit()

        for strategy in strategies:
            if strategy.risk_level == "low":
                await self.apply_strategy(strategy.id, user_id)

        for s in strategies:
            await self.db.refresh(s)
        await self.db.refresh(event)

        return event, strategies

    async def auto_evolve_if_needed(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        diagnosis: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        diagnosis = diagnosis or await self._get_latest_diagnosis_snapshot(user_id, course_id)
        if not diagnosis or not self._should_auto_evolve_from_diagnosis(diagnosis):
            return None

        weak_points = list(diagnosis.get("weak_points") or [])
        focus = (
            "根据最近诊断自动生成学习策略草稿，不自动应用。"
            f"诊断报告ID：{diagnosis.get('id') or 'unknown'}；"
            f"正确率：{float(diagnosis.get('accuracy') or 0):.2f}；"
            f"薄弱点：{weak_points[:5]}"
        )
        event, strategies = await self.analyze(
            user_id=user_id,
            course_id=course_id,
            focus=focus,
            trigger_type="auto_diagnosis",
        )
        return {
            "event_id": str(event.id),
            "strategies_count": len(strategies),
            "strategy_ids": [str(item.id) for item in strategies],
            "status": "draft_generated" if strategies else "no_strategy_generated",
        }

    def _should_auto_evolve_from_diagnosis(self, diagnosis: dict[str, Any]) -> bool:
        if "total_questions" in diagnosis and int(diagnosis.get("total_questions") or 0) == 0 and not diagnosis.get("weak_points"):
            return False
        accuracy = float(diagnosis.get("accuracy") if diagnosis.get("accuracy") is not None else 1.0)
        weak_points = list(diagnosis.get("weak_points") or [])
        return (
            accuracy < settings.evolve_accuracy_threshold
            or len(weak_points) >= settings.evolve_weak_point_min
        )

    async def _get_latest_diagnosis_snapshot(
        self,
        user_id: UUID,
        course_id: UUID,
    ) -> dict[str, Any] | None:
        stmt = (
            select(DiagnosisReport)
            .where(DiagnosisReport.user_id == user_id, DiagnosisReport.course_id == course_id)
            .order_by(DiagnosisReport.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        if report is None:
            return None
        stats = (report.mastery_result or {}).get("summary_stats") or {}
        return {
            "id": str(report.id),
            "accuracy": float(stats.get("accuracy") or 0),
            "total_questions": int(stats.get("total_questions") or 0),
            "weak_points": report.weak_points or [],
        }

    async def list_strategies(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None = None,
        strategy_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[StrategyRead], int]:
        if course_id is not None:
            await self.evaluate_due_strategies(user_id=user_id, course_id=course_id)
        stmt = select(EvolutionStrategy).where(EvolutionStrategy.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(EvolutionStrategy.course_id == course_id)
        if strategy_type is not None:
            stmt = stmt.where(EvolutionStrategy.strategy_type == strategy_type)
        if status is not None:
            stmt = stmt.where(EvolutionStrategy.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(EvolutionStrategy.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        items = [StrategyRead.model_validate(s) for s in result.scalars().all()]
        return items, total

    async def get_strategy(self, strategy_id: UUID, user_id: UUID) -> StrategyRead:
        stmt = select(EvolutionStrategy).where(
            EvolutionStrategy.id == strategy_id,
            EvolutionStrategy.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        strategy = result.scalar_one_or_none()
        if strategy is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="策略不存在",
                status_code=404,
            )
        return StrategyRead.model_validate(strategy)

    async def apply_strategy(
        self, strategy_id: UUID, user_id: UUID,
    ) -> StrategyRead:
        stmt = select(EvolutionStrategy).where(
            EvolutionStrategy.id == strategy_id,
            EvolutionStrategy.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        strategy = result.scalar_one_or_none()
        if strategy is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="策略不存在",
                status_code=404,
            )
        if strategy.status != "draft":
            raise BusinessException(
                code=ErrorCode.BUSINESS_VALIDATION_ERROR,
                detail=f"策略状态为 {strategy.status}，无法应用",
                status_code=422,
            )

        if strategy.previous_strategy_id:
            prev_stmt = select(EvolutionStrategy).where(
                EvolutionStrategy.id == strategy.previous_strategy_id,
            )
            prev_result = await self.db.execute(prev_stmt)
            prev_strategy = prev_result.scalar_one_or_none()
            if prev_strategy and prev_strategy.status == "active":
                prev_strategy.status = "superseded"

        from app.services.strategy_materialization_service import StrategyMaterializationService

        await StrategyMaterializationService(self.db).materialize(strategy)
        strategy.status = "active"
        await self.db.commit()
        await self.db.refresh(strategy)
        return StrategyRead.model_validate(strategy)

    async def rollback_strategy(
        self, strategy_id: UUID, user_id: UUID,
    ) -> StrategyRead:
        stmt = select(EvolutionStrategy).where(
            EvolutionStrategy.id == strategy_id,
            EvolutionStrategy.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        strategy = result.scalar_one_or_none()
        if strategy is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="策略不存在",
                status_code=404,
            )
        if strategy.status != "active":
            raise BusinessException(
                code=ErrorCode.BUSINESS_VALIDATION_ERROR,
                detail=f"策略状态为 {strategy.status}，无法回滚",
                status_code=422,
            )
        if not strategy.previous_strategy_id:
            raise BusinessException(
                code=ErrorCode.BUSINESS_VALIDATION_ERROR,
                detail="该策略没有上一版本，无法回滚",
                status_code=422,
            )

        prev_stmt = select(EvolutionStrategy).where(
            EvolutionStrategy.id == strategy.previous_strategy_id,
        )
        prev_result = await self.db.execute(prev_stmt)
        prev_strategy = prev_result.scalar_one_or_none()
        if prev_strategy is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="上一版本策略不存在",
                status_code=404,
            )

        from app.services.strategy_materialization_service import StrategyMaterializationService

        await StrategyMaterializationService(self.db).materialize(strategy, rollback=True)
        await StrategyMaterializationService(self.db).materialize(prev_strategy)
        strategy.status = "rolled_back"
        prev_strategy.status = "active"
        await self.db.commit()
        await self.db.refresh(prev_strategy)
        return StrategyRead.model_validate(prev_strategy)

    async def list_events(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EventRead], int]:
        stmt = select(EvolutionEvent).where(EvolutionEvent.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(EvolutionEvent.course_id == course_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(EvolutionEvent.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        items = [EventRead.model_validate(e) for e in result.scalars().all()]
        return items, total

    async def evaluate_due_strategies(self, *, user_id: UUID, course_id: UUID) -> int:
        from datetime import UTC, datetime, timedelta

        from app.models.learning_record import LearningRecord

        result = await self.db.execute(select(EvolutionStrategy).where(
            EvolutionStrategy.user_id == user_id,
            EvolutionStrategy.course_id == course_id,
            EvolutionStrategy.status == "active",
            EvolutionStrategy.evaluation_status == "collecting",
        ))
        evaluated = 0
        now = datetime.now(UTC)
        for strategy in result.scalars().all():
            applied_at = strategy.applied_at or strategy.updated_at
            record_count = (await self.db.execute(select(func.count()).select_from(LearningRecord).where(
                LearningRecord.user_id == user_id,
                LearningRecord.course_id == course_id,
                LearningRecord.created_at >= applied_at,
            ))).scalar() or 0
            if record_count < 5 and now - applied_at < timedelta(days=7):
                continue
            strategy.effect_summary = {
                "related_behavior_count": int(record_count),
                "observation_days": max(0, (now - applied_at).days),
                "message": "已达到效果评估窗口；请结合正确率、重复追问、反馈与路径完成率决定是否保留或回滚。",
            }
            strategy.evaluation_status = "ready_for_review"
            strategy.evaluated_at = now
            evaluated += 1
        if evaluated:
            await self.db.commit()
        return evaluated

    async def _get_latest_version(self, user_id: UUID, course_id: UUID) -> int:
        stmt = (
            select(func.max(EvolutionStrategy.version_no))
            .where(
                EvolutionStrategy.user_id == user_id,
                EvolutionStrategy.course_id == course_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _find_active_strategy(
        self, user_id: UUID, course_id: UUID, strategy_type: str,
    ) -> EvolutionStrategy | None:
        stmt = select(EvolutionStrategy).where(
            EvolutionStrategy.user_id == user_id,
            EvolutionStrategy.course_id == course_id,
            EvolutionStrategy.strategy_type == strategy_type,
            EvolutionStrategy.status == "active",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
