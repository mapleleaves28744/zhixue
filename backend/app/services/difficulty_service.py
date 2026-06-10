"""自适应难度调节服务。

根据学生的诊断数据（正确率、薄弱知识点数量）自动计算推荐难度，
并将结果写入 LearningPreference.prompt_params['difficulty']。
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.profile import LearningPreference

logger = logging.getLogger(__name__)

# 难度等级有序列表，从低到高
DIFFICULTY_LEVELS: list[str] = ["easy", "medium", "hard"]

# 错误模式到难度调整的映射
ERROR_PATTERN_ADJUSTMENTS: dict[str, str] = {
    "概念理解偏差": "easy",
    "过程推演不足": "easy",
    "记忆混淆": "easy",
    "迁移能力不足": "medium",
    "表达不完整": "medium",
    "粗心大意": "medium",
    "综合应用薄弱": "medium",
}


class DifficultyService:
    """根据学习诊断数据计算推荐难度。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def compute_and_update(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        accuracy: float,
        weak_points: list[dict[str, Any]],
        error_patterns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """计算推荐难度并写入 LearningPreference。

        返回包含推荐难度和计算依据的字典。
        """
        recommended = self._compute_difficulty(
            accuracy=accuracy,
            weak_points=weak_points,
            error_patterns=error_patterns or [],
        )

        evidence = self._build_evidence(
            accuracy=accuracy,
            weak_points=weak_points,
            error_patterns=error_patterns or [],
            recommended=recommended,
        )

        await self._update_preference(
            user_id=user_id,
            course_id=course_id,
            difficulty=recommended,
        )

        logger.info(
            "Difficulty adjusted for user=%s course=%s: %s (accuracy=%.2f, weak_points=%d)",
            user_id, course_id, recommended, accuracy, len(weak_points),
        )

        return {
            "recommended_difficulty": recommended,
            "evidence": evidence,
            "accuracy": accuracy,
            "weak_points_count": len(weak_points),
        }

    def _compute_difficulty(
        self,
        *,
        accuracy: float,
        weak_points: list[dict[str, Any]],
        error_patterns: list[dict[str, Any]],
    ) -> str:
        """规则引擎：根据多维指标计算推荐难度。"""
        current_idx = DIFFICULTY_LEVELS.index(settings.difficulty_default)

        # 规则 1：正确率过低 → 降低难度
        if accuracy < settings.difficulty_threshold_low:
            current_idx = max(0, current_idx - 1)

        # 规则 2：正确率很高 → 提升难度
        elif accuracy >= settings.difficulty_threshold_high:
            current_idx = min(len(DIFFICULTY_LEVELS) - 1, current_idx + 1)

        # 规则 3：薄弱知识点过多 → 降低难度
        if len(weak_points) >= settings.difficulty_weak_point_trigger:
            current_idx = max(0, current_idx - 1)

        # 规则 4：根据错误模式微调
        if error_patterns:
            dominant_pattern = max(error_patterns, key=lambda p: p.get("count", 0))
            pattern_name = dominant_pattern.get("pattern", "")
            suggested = ERROR_PATTERN_ADJUSTMENTS.get(pattern_name)
            if suggested:
                suggested_idx = DIFFICULTY_LEVELS.index(suggested)
                current_idx = min(current_idx, suggested_idx)

        return DIFFICULTY_LEVELS[current_idx]

    def _build_evidence(
        self,
        *,
        accuracy: float,
        weak_points: list[dict[str, Any]],
        error_patterns: list[dict[str, Any]],
        recommended: str,
    ) -> list[str]:
        """构建推荐依据说明。"""
        evidence: list[str] = []
        evidence.append(f"当前正确率 {accuracy:.0%}")
        evidence.append(f"薄弱知识点 {len(weak_points)} 个")

        if accuracy < settings.difficulty_threshold_low:
            evidence.append(f"正确率低于阈值 {settings.difficulty_threshold_low:.0%}，建议降低难度")
        elif accuracy >= settings.difficulty_threshold_high:
            evidence.append(f"正确率高于阈值 {settings.difficulty_threshold_high:.0%}，建议提升难度")

        if len(weak_points) >= settings.difficulty_weak_point_trigger:
            evidence.append(
                f"薄弱知识点数（{len(weak_points)}）≥ 阈值 "
                f"{settings.difficulty_weak_point_trigger}，建议降低难度"
            )

        if error_patterns:
            top_pattern = max(error_patterns, key=lambda p: p.get("count", 0))
            evidence.append(
                f"主要错误模式：{top_pattern.get('pattern', '未知')}（{top_pattern.get('count', 0)} 次）"
            )

        evidence.append(f"推荐难度：{recommended}")
        return evidence

    async def _update_preference(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        difficulty: str,
    ) -> None:
        """将推荐难度写入 LearningPreference.prompt_params。"""
        stmt = select(LearningPreference).where(
            LearningPreference.user_id == user_id,
            LearningPreference.course_id == course_id,
        )
        result = await self.db.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref is None:
            pref = LearningPreference(
                user_id=user_id,
                course_id=course_id,
                prompt_params={"difficulty": difficulty},
            )
            self.db.add(pref)
        else:
            params = dict(pref.prompt_params or {})
            params["difficulty"] = difficulty
            pref.prompt_params = params

        await self.db.flush()

    async def get_difficulty(self, *, user_id: UUID, course_id: UUID) -> str:
        """读取当前用户的推荐难度，不存在时返回默认值。"""
        stmt = select(LearningPreference.prompt_params).where(
            LearningPreference.user_id == user_id,
            LearningPreference.course_id == course_id,
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row and isinstance(row, dict) and row.get("difficulty"):
            return str(row["difficulty"])
        return settings.difficulty_default
