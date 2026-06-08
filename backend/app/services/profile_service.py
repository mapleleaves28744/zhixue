from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.profile import LearningPreference, StudentProfile
from app.schemas.profile import (
    LearningPreferenceRead,
    ProfileDialogueIngestResult,
    ProfileRead,
    ProfileSummary,
    ProfileUpdate,
)


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_profile(self, user_id: UUID) -> ProfileRead:
        profile = await self._get_or_create(user_id)
        return ProfileRead.model_validate(profile)

    async def update_profile(
        self, user_id: UUID, payload: ProfileUpdate
    ) -> ProfileRead:
        profile = await self._get_or_create(user_id)
        values = payload.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(profile, key, value)
        profile.version_no += 1
        await self.db.commit()
        await self.db.refresh(profile)
        return ProfileRead.model_validate(profile)

    async def get_summary(self, user_id: UUID) -> ProfileSummary:
        profile = await self._get_or_create(user_id)
        return ProfileSummary.model_validate(profile)

    async def ingest_dialogue_profile(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None,
        dialogue_text: str,
        source_message_id: str | None = None,
    ) -> ProfileDialogueIngestResult:
        profile = await self._get_or_create(user_id)
        signals = self._extract_dialogue_profile_signals(dialogue_text)
        evidence = self._build_dialogue_evidence(
            source_message_id=source_message_id,
            dialogue_text=dialogue_text,
        )

        strategy_summary = dict(profile.strategy_summary or {})
        strategy_summary["dialogue_profile"] = self._build_dialogue_profile_summary(
            existing=dict(strategy_summary.get("dialogue_profile") or {}),
            signals=signals,
            evidence=evidence,
        )
        profile.strategy_summary = strategy_summary

        if signals.get("major"):
            profile.major = signals["major"]
        if signals.get("grade"):
            profile.grade = signals["grade"]
        if signals.get("learning_goal"):
            profile.learning_goal = signals["learning_goal"]
        if signals.get("weak_points"):
            profile.weak_points = self._merge_profile_items(
                list(profile.weak_points or []),
                list(signals["weak_points"]),
                key="knowledge_name",
            )
        if signals.get("error_patterns"):
            profile.error_patterns = self._merge_profile_items(
                list(profile.error_patterns or []),
                list(signals["error_patterns"]),
                key="pattern",
            )
        profile.profile_summary = self._compose_dialogue_profile_summary(
            profile=profile,
            signals=signals,
        )
        profile.version_no += 1
        profile.updated_at = datetime.now(UTC)

        preference: LearningPreference | None = None
        if signals.get("preferences"):
            preference = await self._get_or_create_preference(user_id, course_id)
            prefs = dict(signals["preferences"])
            if prefs.get("answer_length"):
                preference.answer_length = prefs["answer_length"]
            if prefs.get("explanation_style"):
                preference.explanation_style = prefs["explanation_style"]
            if prefs.get("resource_preferences"):
                preference.resource_preferences = self._merge_scalar_items(
                    list(preference.resource_preferences or []),
                    list(prefs["resource_preferences"]),
                )
            prompt_params = dict(preference.prompt_params or {})
            prompt_params.update(self._prompt_params_from_preferences(prefs))
            prompt_params["last_dialogue_evidence"] = evidence
            preference.prompt_params = prompt_params
            preference.confidence = Decimal("0.9000")
            preference.version_no += 1
            preference.updated_at = datetime.now(UTC)

        if course_id is not None:
            from app.services.learning_record_service import LearningRecordService

            await LearningRecordService(self.db).record_event(
                user_id=user_id,
                course_id=course_id,
                event_type="profile_updated",
                event_source="profile_service",
                event_payload=self._build_profile_updated_event_payload(
                    signals=signals,
                    source_message_id=source_message_id,
                ),
                commit=False,
            )

        await self.db.commit()
        await self.db.refresh(profile)
        if preference is not None:
            await self.db.refresh(preference)

        if course_id is not None:
            try:
                from app.core.event_bus import get_event_bus

                await get_event_bus().publish(
                    "profile_update",
                    {
                        "user_id": user_id,
                        "course_id": course_id,
                        "accuracy": None,
                        "weak_points": list(signals.get("weak_points") or []),
                    },
                    source="profile_service",
                )
            except Exception:
                pass

        return ProfileDialogueIngestResult(
            profile=ProfileRead.model_validate(profile),
            preferences=LearningPreferenceRead.model_validate(preference) if preference else None,
            signals=signals,
            evidence=evidence,
        )

    async def rebuild(self, user_id: UUID) -> ProfileRead:
        from app.agents.context import AgentContext
        from app.agents.profile_agent import ProfileAgent

        agent = ProfileAgent(self.db)
        context = AgentContext(
            user_id=user_id,
            course_id=user_id,
            task_type="profile_rebuild",
            params={"action": "rebuild"},
        )
        result = await agent.run(context)
        if not result.success:
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=result.message,
                status_code=500,
            )
        profile = await self._get_or_create(user_id)
        return ProfileRead.model_validate(profile)

    def _build_profile_updated_event_payload(
        self,
        *,
        signals: dict[str, Any],
        source_message_id: str | None,
    ) -> dict[str, Any]:
        changed_fields = [
            key
            for key in ("major", "grade", "learning_goal", "preferences", "weak_points", "error_patterns")
            if signals.get(key)
        ]
        return {
            "source": "dialogue_ingest",
            "changed_fields": changed_fields,
            "source_message_id": source_message_id,
        }

    async def get_preferences(
        self, user_id: UUID, course_id: UUID | None = None
    ) -> list[LearningPreferenceRead]:
        stmt = select(LearningPreference).where(
            LearningPreference.user_id == user_id
        )
        if course_id is not None:
            stmt = stmt.where(LearningPreference.course_id == course_id)
        result = await self.db.execute(stmt)
        prefs = result.scalars().all()
        return [LearningPreferenceRead.model_validate(p) for p in prefs]

    def _extract_dialogue_profile_signals(self, dialogue_text: str) -> dict[str, Any]:
        text = " ".join(str(dialogue_text or "").split())
        compact = re.sub(r"\s+", "", text)
        signals: dict[str, Any] = {
            "major": None,
            "grade": None,
            "learning_goal": None,
            "preferences": {},
            "weak_points": [],
            "error_patterns": [],
        }

        for major in (
            "软件工程",
            "计算机科学与技术",
            "计算机",
            "人工智能",
            "数据科学",
            "信息管理",
            "电子信息",
            "数学",
            "统计学",
        ):
            if major in compact:
                signals["major"] = "计算机类" if major == "计算机" else major
                break

        for grade in (
            "大一",
            "大二",
            "大三",
            "大四",
            "研一",
            "研二",
            "研三",
            "研究生一年级",
            "研究生二年级",
        ):
            if grade in compact:
                signals["grade"] = grade
                break

        goal_match = re.search(
            r"(?:学习目标|目标|希望|想要|想|准备|为了|要)(?:是|：|:)?([^。；;\n]{2,80})",
            text,
        )
        if goal_match:
            signals["learning_goal"] = goal_match.group(1).strip(" ，,。")

        preferences: dict[str, Any] = {}
        if any(word in compact for word in ("短一点", "简洁", "短回答", "短总结", "别太长")):
            preferences["answer_length"] = "short"
        elif any(word in compact for word in ("详细", "深入", "完整", "展开讲")):
            preferences["answer_length"] = "long"

        resource_preferences: list[str] = []
        lowered = text.lower()
        if "python" in lowered or "代码" in compact or "实现" in compact:
            preferences["explanation_style"] = "code_first"
            resource_preferences.append("python_code")
        elif any(word in compact for word in ("图示", "可视化", "画图", "图解")):
            preferences["explanation_style"] = "visual_first"
            resource_preferences.append("visual_explanation")
        elif any(word in compact for word in ("分步骤", "一步一步", "步骤化")):
            preferences["explanation_style"] = "step_by_step"
        elif any(word in compact for word in ("例子", "案例", "例题")):
            preferences["explanation_style"] = "example_first"

        if any(word in compact for word in ("图示", "可视化", "画图", "图解")):
            resource_preferences.append("visual_explanation")
        if any(word in compact for word in ("分步骤", "一步一步", "步骤化")):
            resource_preferences.append("step_by_step")
        if any(word in compact for word in ("总结", "卡片", "速记")):
            resource_preferences.append("summary_card")
        if any(word in compact for word in ("练习", "刷题", "题目")):
            resource_preferences.append("practice_first")
        if any(word in compact for word in ("对比", "表格", "易混")):
            resource_preferences.append("comparison_table")
        if resource_preferences:
            preferences["resource_preferences"] = self._merge_scalar_items([], resource_preferences)
        signals["preferences"] = preferences

        weak_topics = [
            ("图的最短路径", ("图的最短路径", "最短路径")),
            ("递归", ("递归",)),
            ("二叉树遍历", ("二叉树遍历", "树遍历")),
            ("栈与队列", ("栈与队列",)),
            ("栈", ("栈",)),
            ("队列", ("队列",)),
            ("链表", ("链表",)),
            ("树", ("树", "二叉树")),
            ("图", ("图", "图论")),
            ("排序", ("排序",)),
            ("哈希", ("哈希", "散列表")),
            ("复杂度分析", ("复杂度", "时间复杂度")),
        ]
        weak_markers = ("薄弱", "不会", "不懂", "混淆", "容易错", "经常错", "补弱", "困难", "难")
        has_weak_marker = any(marker in compact for marker in weak_markers)
        for name, aliases in weak_topics:
            if any(alias in compact for alias in aliases) and has_weak_marker:
                existing_names = {item["knowledge_name"] for item in signals["weak_points"]}
                if name == "树" and any(item.startswith("二叉树") for item in existing_names):
                    continue
                if name == "图" and any(item.startswith("图的") for item in existing_names):
                    continue
                if name in {"栈", "队列"} and "栈与队列" in existing_names:
                    continue
                signals["weak_points"].append(
                    {
                        "knowledge_name": name,
                        "reason": "来自对话中学生主动表达的薄弱点或补弱目标。",
                        "confidence": 0.88,
                        "source": "dialogue",
                    }
                )

        pattern_rules = [
            ("边界条件遗漏", ("边界条件", "终止条件", "漏掉边界")),
            ("概念混淆", ("概念混淆", "混淆", "分不清")),
            ("指针引用错误", ("指针", "引用", "next")),
            ("复杂度分析困难", ("复杂度", "时间复杂度", "空间复杂度")),
            ("代码实现步骤缺失", ("代码写不出来", "实现困难", "步骤缺失")),
        ]
        for pattern, aliases in pattern_rules:
            if any(alias in compact for alias in aliases):
                signals["error_patterns"].append(
                    {
                        "pattern": pattern,
                        "reason": "来自对话中学生主动描述的错误模式。",
                        "confidence": 0.84,
                        "source": "dialogue",
                    }
                )

        return signals

    def _build_dialogue_evidence(
        self,
        *,
        source_message_id: str | None,
        dialogue_text: str,
    ) -> dict[str, Any]:
        quote = " ".join(str(dialogue_text or "").split())[:180]
        return {
            "source_type": "agent_dialogue",
            "source_message_id": source_message_id,
            "quote": quote,
            "observed_at": datetime.now(UTC).isoformat(),
            "method": "phase4_dialogue_profile_extraction",
        }

    def _build_dialogue_profile_summary(
        self,
        *,
        existing: dict[str, Any],
        signals: dict[str, Any],
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        dimensions = dict(existing.get("dimensions") or {})

        def upsert_dimension(
            key: str,
            *,
            value: Any | None = None,
            items: list[Any] | None = None,
            confidence: float = 0.86,
        ) -> None:
            current = dict(dimensions.get(key) or {})
            current["confidence"] = max(float(current.get("confidence") or 0), confidence)
            if value is not None:
                current["value"] = value
            if items is not None:
                merge_key = "knowledge_name" if key == "weak_points" else "pattern"
                current["items"] = self._merge_profile_items(
                    list(current.get("items") or []),
                    items,
                    key=merge_key,
                )
            evidences = list(current.get("evidence") or [])
            if not any(item.get("source_message_id") == evidence.get("source_message_id") for item in evidences if isinstance(item, dict)):
                evidences.append(evidence)
            current["evidence"] = evidences[-5:]
            dimensions[key] = current

        if signals.get("major"):
            upsert_dimension("major", value=signals["major"], confidence=0.9)
        if signals.get("grade"):
            upsert_dimension("grade", value=signals["grade"], confidence=0.9)
        if signals.get("learning_goal"):
            upsert_dimension("learning_goal", value=signals["learning_goal"], confidence=0.86)

        prefs = dict(signals.get("preferences") or {})
        if prefs.get("answer_length"):
            upsert_dimension("answer_length", value=prefs["answer_length"], confidence=0.84)
        if prefs.get("explanation_style"):
            upsert_dimension("explanation_style", value=prefs["explanation_style"], confidence=0.88)
        if prefs.get("resource_preferences"):
            upsert_dimension("resource_preferences", items=[{"pattern": item} for item in prefs["resource_preferences"]], confidence=0.84)
        if signals.get("weak_points"):
            upsert_dimension("weak_points", items=list(signals["weak_points"]), confidence=0.88)
        if signals.get("error_patterns"):
            upsert_dimension("error_patterns", items=list(signals["error_patterns"]), confidence=0.84)

        source_ids = {
            str(item.get("source_message_id") or item.get("quote"))
            for dim in dimensions.values()
            for item in (dim.get("evidence") or [])
            if isinstance(item, dict)
        }
        return {
            "phase": "phase4_dialogue_profile",
            "dimensions": dimensions,
            "source_count": len(source_ids),
            "last_dialogue_update_at": evidence["observed_at"],
        }

    def _compose_dialogue_profile_summary(
        self,
        *,
        profile: StudentProfile,
        signals: dict[str, Any],
    ) -> str:
        parts: list[str] = []
        identity = " ".join(str(item) for item in (profile.grade, profile.major) if item)
        if identity:
            parts.append(f"学生身份：{identity}。")
        if profile.learning_goal:
            parts.append(f"学习目标：{profile.learning_goal}。")
        weak_points = [item.get("knowledge_name") for item in signals.get("weak_points") or [] if isinstance(item, dict)]
        if weak_points:
            parts.append(f"对话中主动提到的薄弱点：{'、'.join(weak_points[:4])}。")
        prefs = dict(signals.get("preferences") or {})
        style = prefs.get("explanation_style")
        if style:
            style_label = {
                "code_first": "代码示例优先",
                "visual_first": "图示化解释优先",
                "step_by_step": "分步骤讲解",
                "example_first": "例题驱动",
            }.get(style, str(style))
            parts.append(f"偏好：{style_label}。")
        return "".join(parts) or profile.profile_summary or "画像已接入对话式更新，后续会继续累积证据。"

    def _prompt_params_from_preferences(self, preferences: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        answer_length = preferences.get("answer_length")
        if answer_length:
            params["answer_length"] = answer_length
        style = preferences.get("explanation_style")
        if style == "code_first":
            params.update({"include_code_example": True, "explanation_style": "code_first"})
        elif style == "visual_first":
            params.update({"include_visual_description": True, "explanation_style": "visual_first"})
        elif style == "step_by_step":
            params.update({"include_step_by_step": True, "explanation_style": "step_by_step"})
        elif style == "example_first":
            params.update({"include_examples": True, "explanation_style": "example_first"})
        resources = set(preferences.get("resource_preferences") or [])
        if "comparison_table" in resources:
            params["include_comparison_table"] = True
        if "summary_card" in resources:
            params["include_summary_card"] = True
        if "practice_first" in resources:
            params["include_practice_prompt"] = True
        return params

    def _merge_profile_items(
        self,
        existing: list[Any],
        incoming: list[Any],
        *,
        key: str,
    ) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for item in incoming + existing:
            if not isinstance(item, dict):
                identity = str(item)
                payload: Any = item
            else:
                identity = str(item.get(key) or item.get("name") or item)
                payload = item
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(payload)
        return merged[:12]

    def _merge_scalar_items(self, existing: list[Any], incoming: list[Any]) -> list[Any]:
        result: list[Any] = []
        seen: set[str] = set()
        for item in existing + incoming:
            value = str(item)
            if value in seen:
                continue
            seen.add(value)
            result.append(item)
        return result[:12]

    async def _get_or_create(self, user_id: UUID) -> StudentProfile:
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = StudentProfile(user_id=user_id)
            self.db.add(profile)
            await self.db.commit()
            await self.db.refresh(profile)
        return profile

    async def _get_or_create_preference(
        self,
        user_id: UUID,
        course_id: UUID | None,
    ) -> LearningPreference:
        stmt = select(LearningPreference).where(LearningPreference.user_id == user_id)
        if course_id is None:
            stmt = stmt.where(LearningPreference.course_id.is_(None))
        else:
            stmt = stmt.where(LearningPreference.course_id == course_id)
        result = await self.db.execute(stmt)
        preference = result.scalar_one_or_none()
        if preference is None:
            preference = LearningPreference(user_id=user_id, course_id=course_id)
            self.db.add(preference)
            await self.db.flush()
        return preference
