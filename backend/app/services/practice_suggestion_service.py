"""根据用户最近在 AI 助手的提问，推荐练习知识点。"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_conversation import AgentConversation, AgentMessage
from app.models.user import User
from app.repositories.quiz_repository import QuizRepository
from app.services.course_service import CourseService

_TOPIC_KEYWORDS: tuple[str, ...] = (
    "链表",
    "单链表",
    "双链表",
    "栈",
    "队列",
    "循环队列",
    "二叉树",
    "满二叉树",
    "完全二叉树",
    "线索二叉树",
    "哈夫曼树",
    "图",
    "有向图",
    "无向图",
    "哈希表",
    "哈希",
    "散列",
    "排序",
    "快排",
    "归并排序",
    "堆排序",
    "查找",
    "二分查找",
    "遍历",
    "先序遍历",
    "中序遍历",
    "后序遍历",
    "层序遍历",
    "广度优先",
    "深度优先",
    "BFS",
    "DFS",
    "递归",
    "数组",
    "字符串",
    "树",
    "堆",
    "红黑树",
    "平衡二叉树",
    "邻接表",
    "邻接矩阵",
    "拓扑排序",
    "最短路径",
    "最小生成树",
)

_SKIP_PHRASES = (
    "你好",
    "谢谢",
    "再见",
    "登录",
    "注册",
)


class PracticeSuggestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def suggest(
        self,
        *,
        current_user: User,
        course_id: UUID,
        limit: int = 12,
        trigger_prepush: bool = True,
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        questions = await self._recent_user_questions(current_user.id, course_id, limit=limit)
        topics = self._extract_topics(questions)
        latest_topics = self._topics_from_text(questions[0]) if questions else []
        raw_primary = latest_topics[0] if latest_topics else (topics[0] if topics else "数据结构")
        primary = self._normalize_topic_label(raw_primary, questions[0] if questions else "")
        reason = self._build_reason(questions, primary)
        existing_quiz_id = await self._find_recent_quiz_for_topic(
            user_id=current_user.id,
            course_id=course_id,
            topic=primary,
        )
        from app.services.practice_prepush_service import PracticePrepushService

        prepush = PracticePrepushService(self.db)
        if existing_quiz_id is None:
            existing_quiz_id = await prepush.get_cached_quiz_id(
                user_id=current_user.id,
                course_id=course_id,
                topic=primary,
            )
        prepush_status = await prepush.get_prepush_status(
            user_id=current_user.id,
            course_id=course_id,
            topic=primary,
            existing_quiz_id=existing_quiz_id,
        )
        if (
            trigger_prepush
            and bool(questions)
            and existing_quiz_id is None
            and prepush_status == "none"
        ):
            await prepush.enqueue(
                user_id=current_user.id,
                course_id=course_id,
                topic=primary,
            )
            prepush_status = "generating"
        return {
            "primary_topic": primary,
            "topics": topics[:5],
            "recent_questions": questions[:5],
            "reason": reason,
            "should_suggest": bool(questions),
            "existing_quiz_id": str(existing_quiz_id) if existing_quiz_id else None,
            "prepush_status": prepush_status,
        }

    async def _recent_user_questions(
        self,
        user_id: UUID,
        course_id: UUID,
        *,
        limit: int,
    ) -> list[str]:
        stmt = (
            select(AgentMessage.content)
            .join(AgentConversation, AgentMessage.conversation_id == AgentConversation.id)
            .where(
                AgentMessage.user_id == user_id,
                AgentMessage.role == "user",
                AgentConversation.course_id == course_id,
            )
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        cleaned: list[str] = []
        seen: set[str] = set()
        for text in rows:
            value = str(text or "").strip()
            if len(value) < 4 or value in seen:
                continue
            if any(phrase in value for phrase in _SKIP_PHRASES):
                continue
            seen.add(value)
            cleaned.append(value[:240])

        from app.models.learning_record import LearningRecord

        tutor_stmt = (
            select(LearningRecord.event_payload)
            .where(
                LearningRecord.user_id == user_id,
                LearningRecord.course_id == course_id,
                LearningRecord.event_type == "chat",
            )
            .order_by(LearningRecord.created_at.desc())
            .limit(limit)
        )
        for payload in (await self.db.execute(tutor_stmt)).scalars().all():
            if not isinstance(payload, dict):
                continue
            value = str(payload.get("question") or "").strip()
            if len(value) < 4 or value in seen:
                continue
            if any(phrase in value for phrase in _SKIP_PHRASES):
                continue
            seen.add(value)
            cleaned.append(value[:240])
        return cleaned[:limit]

    def _extract_topics(self, questions: list[str]) -> list[str]:
        counter: Counter[str] = Counter()
        total = len(questions)
        for index, question in enumerate(questions):
            weight = max(1, total - index)
            for topic in self._topics_from_text(question):
                counter[topic] += weight
        if not counter:
            return []
        return [topic for topic, _ in counter.most_common()]

    def _topics_from_text(self, text: str) -> list[str]:
        found: list[str] = []
        lowered = text.lower()
        for keyword in _TOPIC_KEYWORDS:
            if keyword.lower() in lowered or keyword in text:
                found.append(keyword)
        for match in re.finditer(r"\b(Python|Java|Go|Rust|Redis|MySQL|JavaScript|TypeScript)\s*[\d.]+", text, re.I):
            snippet = match.group(0).strip()
            if snippet not in found:
                found.append(snippet)
        for match in re.finditer(r"(?:联网搜索|网上搜索|搜索|查一下)\s*([A-Za-z0-9.\u4e00-\u9fa5]{2,16})", text):
            snippet = self._normalize_topic_label(match.group(1).strip(" 的？?"), text)
            if snippet and snippet not in found:
                found.append(snippet)
        for match in re.finditer(r"关于(.{1,12}?)(?:的|练习|题|ppt|讲解|思维导图|视频|课件)", text):
            snippet = match.group(1).strip(" 的")
            if snippet and snippet not in found:
                found.append(snippet)
        for match in re.finditer(r"(什么是|解释一下|讲解一下|介绍一下)(.{1,12})", text):
            snippet = match.group(2).strip("？? ")
            if snippet and snippet not in found:
                found.append(snippet)
        return found

    def _normalize_topic_label(self, topic: str, source_question: str = "") -> str:
        value = str(topic or source_question or "").strip()
        combined = f"{value} {source_question}".strip()
        value = re.sub(r"^(联网搜索|网上搜索|在线搜索|搜索|查一下)\s*", "", value, flags=re.I)
        value = re.sub(
            r"(有哪些新特性|有什么新功能|是什么|怎么用|有哪些|解释一下|讲解一下).*$",
            "",
            value,
            flags=re.I,
        ).strip(" 的？?，,")
        version_match = re.search(
            r"\b(Python|Java|Go|Rust|Redis|MySQL|JavaScript|TypeScript)\s*[\d.]+",
            combined,
            re.I,
        )
        if version_match:
            return version_match.group(0).strip()
        if value in _TOPIC_KEYWORDS or any(keyword in value for keyword in _TOPIC_KEYWORDS):
            for keyword in _TOPIC_KEYWORDS:
                if keyword in value:
                    return keyword
        if len(value) > 14:
            return value[:14].rstrip() + "…"
        return value or "数据结构"

    def _question_preview(self, question: str, *, max_len: int = 22) -> str:
        preview = re.sub(r"^(联网搜索|网上搜索|搜索|查一下)\s*", "", question.strip(), flags=re.I)
        preview = re.sub(r"(有哪些新特性|有什么新功能).*$", "", preview, flags=re.I).strip(" 的？?")
        if len(preview) > max_len:
            return preview[:max_len].rstrip() + "…"
        return preview

    def _build_reason(self, questions: list[str], primary_topic: str) -> str:
        if not questions:
            return "暂无最近提问，可直接选择知识点生成练习。"
        preview = self._question_preview(questions[0])
        if preview and preview != primary_topic:
            return f"你刚在助手问过「{preview}」，将围绕「{primary_topic}」生成配套练习。"
        return f"你最近在助手关注「{primary_topic}」，将自动生成配套练习。"

    async def _find_recent_quiz_for_topic(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        topic: str,
    ) -> UUID | None:
        items, _ = await QuizRepository(self.db).list_quizzes(
            user_id=user_id,
            course_id=course_id,
            page=1,
            page_size=5,
        )
        for quiz in items:
            if quiz.status == "submitted":
                continue
            title = str(quiz.title or "")
            if self._topic_matches_quiz_title(topic, title):
                return quiz.id
        return None

    @staticmethod
    def _topic_matches_quiz_title(topic: str, title: str) -> bool:
        normalized_topic = topic.strip()
        normalized_title = title.strip()
        if not normalized_topic or not normalized_title:
            return False
        if normalized_topic in normalized_title or normalized_title in normalized_topic:
            return True
        base_topic = re.sub(r"\s*[\d.]+\s*", " ", normalized_topic, flags=re.I).strip()
        base_title = re.sub(r"\s*[\d.]+\s*", " ", normalized_title, flags=re.I).strip()
        return bool(base_topic) and base_topic.lower() in base_title.lower()
