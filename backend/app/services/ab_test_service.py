"""A/B 测试服务。

管理实验的创建、用户分组、指标记录和胜出判定。
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.ab_test import ABTest, ABTestAssignment

logger = logging.getLogger(__name__)


class ABTestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_test(
        self,
        *,
        course_id: UUID,
        name: str,
        test_type: str = "strategy",
        control_config: dict[str, Any],
        treatment_config: dict[str, Any],
        traffic_split: float = 0.5,
        description: str = "",
    ) -> ABTest:
        test = ABTest(
            course_id=course_id,
            name=name,
            description=description,
            test_type=test_type,
            control_config=control_config,
            treatment_config=treatment_config,
            traffic_split=max(0.0, min(1.0, traffic_split)),
            status="draft",
        )
        self.db.add(test)
        await self.db.flush()
        return test

    async def start_test(self, test_id: UUID) -> ABTest:
        test = await self._get_test(test_id)
        if test.status != "draft":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail=f"只有 draft 状态的实验可以启动，当前状态: {test.status}",
                status_code=400,
            )
        test.status = "running"
        await self.db.flush()
        return test

    async def pause_test(self, test_id: UUID) -> ABTest:
        test = await self._get_test(test_id)
        if test.status != "running":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="只有 running 状态的实验可以暂停",
                status_code=400,
            )
        test.status = "paused"
        await self.db.flush()
        return test

    async def assign_user(self, test_id: UUID, user_id: UUID) -> str:
        """为用户分配实验组。确定性分配：基于 hash(user_id + test_id)。"""
        existing_group = await self._get_assignment_group(test_id, user_id)
        if existing_group is not None:
            return existing_group

        test = await self._get_test(test_id)
        if test.status != "running":
            return "control"  # 未运行的实验默认对照组

        group = self._deterministic_group(user_id, test_id, test.traffic_split)
        insert_stmt = (
            insert(ABTestAssignment)
            .values(test_id=test_id, user_id=user_id, group=group)
            .on_conflict_do_nothing(index_elements=["test_id", "user_id"])
        )
        await self.db.execute(insert_stmt)
        await self.db.flush()

        assigned_group = await self._get_assignment_group(test_id, user_id)
        return assigned_group if assigned_group is not None else group

    async def get_user_config(
        self,
        test_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        """获取用户的实验配置（对照组或实验组）。"""
        group = await self.assign_user(test_id, user_id)
        test = await self._get_test(test_id)
        if group == "treatment":
            return dict(test.treatment_config)
        return dict(test.control_config)

    async def record_metric(
        self,
        test_id: UUID,
        user_id: UUID,
        metric_value: float,
    ) -> None:
        """记录用户的实验指标值。"""
        await self._get_test(test_id)
        existing_group = await self._get_assignment_group(test_id, user_id)
        if existing_group is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="用户尚未分配到该实验，无法记录指标",
                status_code=404,
            )

        stmt = (
            update(ABTestAssignment)
            .where(
                ABTestAssignment.test_id == test_id,
                ABTestAssignment.user_id == user_id,
            )
            .values(metric_value=metric_value)
        )
        result = await self.db.execute(stmt)
        if getattr(result, "rowcount", 0) == 0:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="用户尚未分配到该实验，无法记录指标",
                status_code=404,
            )
        await self.db.flush()

    async def complete_test(self, test_id: UUID) -> ABTest:
        """完成实验并自动判定胜出组。"""
        test = await self._get_test(test_id)

        # 计算各组平均指标
        stmt = (
            select(
                ABTestAssignment.group,
                func.count(ABTestAssignment.id).label("count"),
                func.avg(ABTestAssignment.metric_value).label("avg_metric"),
            )
            .where(ABTestAssignment.test_id == test_id)
            .group_by(ABTestAssignment.group)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        stats: dict[str, dict[str, float]] = {}
        for group, count, avg_metric in rows:
            stats[group] = {
                "count": count,
                "avg_metric": round(float(avg_metric or 0), 4),
            }

        # 判定胜出
        control_avg = stats.get("control", {}).get("avg_metric", 0)
        treatment_avg = stats.get("treatment", {}).get("avg_metric", 0)

        if treatment_avg > control_avg:
            test.winner = "treatment"
        elif control_avg > treatment_avg:
            test.winner = "control"
        else:
            test.winner = None  # 平局

        test.status = "completed"
        await self.db.flush()

        logger.info(
            "AB test %s completed: winner=%s, control_avg=%.4f, treatment_avg=%.4f",
            test_id, test.winner, control_avg, treatment_avg,
        )
        return test

    async def get_test_stats(self, test_id: UUID) -> dict[str, Any]:
        """获取实验统计数据。"""
        test = await self._get_test(test_id)

        stmt = (
            select(
                ABTestAssignment.group,
                func.count(ABTestAssignment.id).label("count"),
                func.avg(ABTestAssignment.metric_value).label("avg_metric"),
                func.min(ABTestAssignment.metric_value).label("min_metric"),
                func.max(ABTestAssignment.metric_value).label("max_metric"),
            )
            .where(ABTestAssignment.test_id == test_id)
            .group_by(ABTestAssignment.group)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        groups: dict[str, dict[str, float]] = {}
        for group, count, avg_metric, min_metric, max_metric in rows:
            groups[group] = {
                "count": count,
                "avg_metric": round(float(avg_metric or 0), 4),
                "min_metric": round(float(min_metric or 0), 4),
                "max_metric": round(float(max_metric or 0), 4),
            }

        return {
            "test_id": str(test.id),
            "name": test.name,
            "status": test.status,
            "winner": test.winner,
            "groups": groups,
        }

    async def list_tests(
        self,
        course_id: UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ABTest], int]:
        stmt = select(ABTest)
        if course_id:
            stmt = stmt.where(ABTest.course_id == course_id)
        if status:
            stmt = stmt.where(ABTest.status == status)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(total_stmt)).scalar() or 0
        stmt = stmt.order_by(ABTest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def _get_assignment_group(self, test_id: UUID, user_id: UUID) -> str | None:
        stmt = select(ABTestAssignment.group).where(
            ABTestAssignment.test_id == test_id,
            ABTestAssignment.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _deterministic_group(user_id: UUID, test_id: UUID, traffic_split: float) -> str:
        hash_input = f"{user_id}:{test_id}".encode()
        hash_val = int(hashlib.md5(hash_input).hexdigest(), 16) % 10000
        return "treatment" if hash_val < traffic_split * 10000 else "control"

    async def _get_test(self, test_id: UUID) -> ABTest:
        test = await self.db.get(ABTest, test_id)
        if test is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="实验不存在", status_code=404)
        return test
