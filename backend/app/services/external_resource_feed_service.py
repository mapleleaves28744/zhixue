"""主页个性化外部学习资源推送（AnySearch + Redis 缓存）。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.diagnosis import DiagnosisReport
from app.models.learning_path import LearningPath
from app.models.user import User
from app.services.course_service import CourseService
from app.services.diagnosis_service import DiagnosisService
from app.services.learning_path_service import LearningPathService
from app.services.practice_suggestion_service import PracticeSuggestionService
from app.services.web_search_service import WebSearchService

logger = logging.getLogger(__name__)

ExternalResourceKind = Literal["video", "blog", "repo"]

_CACHE_TTL_SECONDS = 6 * 3600
_MAX_TOPICS = 5
_MAX_FEED_ITEMS = 15
_SEARCH_SPECS: tuple[tuple[ExternalResourceKind, str, str | None], ...] = (
    ("video", "{topic} 教程 讲解", "bilibili.com"),
    ("blog", "{topic} 技术博客 深入理解", None),
    ("repo", "{topic} site:github.com", "github.com"),
)


class ExternalResourceFeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_feed(
        self,
        *,
        current_user: User,
        course_id: UUID,
        refresh: bool = False,
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        topics, topic_reason = await self._resolve_topics(current_user, course_id)
        primary_topic = topics[0] if topics else "数据结构"
        cache_key = self._cache_key(current_user.id, course_id, topics)

        if not refresh:
            cached = await self._load_cache(cache_key)
            if cached is not None:
                cached["cached"] = True
                cached["prepush_status"] = "ready"
                return cached

        search_service = WebSearchService()
        if not search_service.enabled:
            return {
                "primary_topic": primary_topic,
                "topics": topics,
                "reason": topic_reason,
                "items": [],
                "cached": False,
                "prepush_status": "none",
                "provider": "anysearch",
                "message": "未配置 ANYSEARCH_API_KEY，暂无法推送外部学习资源。",
            }

        if refresh:
            payload = await self.generate_and_cache(
                current_user=current_user,
                course_id=course_id,
                expected_cache_key=cache_key,
            )
            payload["cached"] = False
            payload["prepush_status"] = "ready" if payload.get("items") else "none"
            return payload

        from app.services.external_resource_prepush_service import ExternalResourcePrepushService

        prepush = ExternalResourcePrepushService(self.db)
        if await prepush.is_generating(cache_key):
            return self._prepush_pending_payload(
                primary_topic=primary_topic,
                topics=topics,
                reason=topic_reason,
            )

        await prepush.enqueue(
            user_id=current_user.id,
            course_id=course_id,
            cache_key=cache_key,
        )
        return self._prepush_pending_payload(
            primary_topic=primary_topic,
            topics=topics,
            reason=topic_reason,
        )

    async def generate_and_cache(
        self,
        *,
        current_user: User,
        course_id: UUID,
        expected_cache_key: str | None = None,
    ) -> dict[str, Any]:
        topics, topic_reason = await self._resolve_topics(current_user, course_id)
        primary_topic = topics[0] if topics else "数据结构"
        cache_key = expected_cache_key or self._cache_key(current_user.id, course_id, topics)

        search_service = WebSearchService()
        if not search_service.enabled:
            return {
                "primary_topic": primary_topic,
                "topics": topics,
                "reason": topic_reason,
                "items": [],
                "cached": False,
                "prepush_status": "none",
                "provider": "anysearch",
                "message": "未配置 ANYSEARCH_API_KEY，暂无法推送外部学习资源。",
            }

        items = await self._search_for_topics(search_service, topics=topics)
        payload = {
            "primary_topic": primary_topic,
            "topics": topics,
            "reason": topic_reason,
            "items": items,
            "cached": False,
            "prepush_status": "ready" if items else "none",
            "provider": "anysearch",
            "message": "" if items else "暂未检索到合适的外部资源，可先在助手提问或换一批重试。",
        }
        if items:
            await self._save_cache(cache_key, payload)
        return payload

    @staticmethod
    def _prepush_pending_payload(
        *,
        primary_topic: str,
        topics: list[str],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "primary_topic": primary_topic,
            "topics": topics,
            "reason": reason,
            "items": [],
            "cached": False,
            "prepush_status": "generating",
            "provider": "anysearch",
            "message": "资源已在后台准备，通常几秒内即可查看。",
        }

    async def _resolve_topics(self, current_user: User, course_id: UUID) -> tuple[list[str], str]:
        suggestion = await PracticeSuggestionService(self.db).suggest(
            current_user=current_user,
            course_id=course_id,
            trigger_prepush=False,
        )
        from_chat: list[str] = []
        if suggestion.get("primary_topic"):
            from_chat.append(str(suggestion["primary_topic"]))
        from_chat.extend(str(item) for item in (suggestion.get("topics") or []))
        for question in suggestion.get("recent_questions") or []:
            from_chat.extend(PracticeSuggestionService(self.db)._topics_from_text(str(question)))

        weak_points = await self._weak_point_names(current_user.id, course_id)
        path_titles = await self._path_item_titles(current_user, course_id)
        topics = self.merge_topics(from_chat, weak_points, path_titles, ["数据结构"], limit=_MAX_TOPICS)
        return topics, self._build_topics_reason(topics)

    @staticmethod
    def merge_topics(*sources: list[str], limit: int = _MAX_TOPICS) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for source in sources:
            for raw in source:
                topic = str(raw or "").strip()
                if not topic:
                    continue
                key = topic.lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(topic)
                if len(merged) >= limit:
                    return merged
        return merged

    @staticmethod
    def _build_topics_reason(topics: list[str]) -> str:
        if not topics:
            return "暂未识别到个性化主题，先为你推送数据结构相关的外部资源。"
        if len(topics) == 1:
            return f"根据你最近在助手的提问，围绕「{topics[0]}」推送外部资源。"
        preview = "、".join(f"「{topic}」" for topic in topics[:4])
        suffix = f" 等 {len(topics)} 个知识点" if len(topics) > 4 else ""
        return f"综合最近提问、薄弱点与学习路径，围绕 {preview}{suffix} 推送 B 站视频、技术博客与 GitHub 项目。"

    async def _weak_point_names(self, user_id: UUID, course_id: UUID) -> list[str]:
        names: list[str] = []
        report_stmt = (
            select(DiagnosisReport)
            .where(
                DiagnosisReport.user_id == user_id,
                DiagnosisReport.course_id == course_id,
            )
            .order_by(DiagnosisReport.created_at.desc())
            .limit(1)
        )
        report = (await self.db.execute(report_stmt)).scalar_one_or_none()
        if report and isinstance(report.weak_points, list):
            for item in report.weak_points[:4]:
                if isinstance(item, dict):
                    name = str(item.get("knowledge_name") or item.get("name") or "").strip()
                    if name:
                        names.append(name)

        mastery = await DiagnosisService(self.db).get_mastery(user_id=user_id, course_id=course_id)
        mastery_items = sorted(
            list(mastery.get("items") or []),
            key=lambda item: float(item.get("mastery_level") or 1),
        )
        for item in mastery_items[:4]:
            name = str(item.get("knowledge_name") or "").strip()
            if name:
                names.append(name)
        return self.merge_topics(names, limit=_MAX_TOPICS)

    async def _path_item_titles(self, current_user: User, course_id: UUID) -> list[str]:
        paths, _ = await LearningPathService(self.db).list_paths(
            current_user=current_user,
            course_id=course_id,
            page=1,
            page_size=5,
        )
        path = next((item for item in paths if item.status == "active"), paths[0] if paths else None)
        if path is None:
            return []
        items = sorted(path.items or [], key=lambda item: int(item.order_index or 0))
        titles: list[str] = []
        for item in items:
            if item.status in {"doing", "pending", "completed"}:
                title = str(item.title or "").strip()
                if title:
                    titles.append(title)
        if not titles and path.title:
            titles.append(str(path.title).strip())
        return self.merge_topics(titles, limit=_MAX_TOPICS)

    async def _search_for_topics(
        self,
        search_service: WebSearchService,
        *,
        topics: list[str],
    ) -> list[dict[str, str]]:
        if not topics:
            topics = ["数据结构"]

        tasks: list[Any] = []
        for index, topic in enumerate(topics):
            kind, _template, domain = _SEARCH_SPECS[index % len(_SEARCH_SPECS)]
            item_reason = f"基于知识点「{topic}」推荐"
            tasks.append(
                self._search_kind(
                    search_service,
                    kind=kind,
                    topic=topic,
                    domain=domain,
                    item_reason=item_reason,
                    max_results=2,
                )
            )
            if index == 0:
                for extra_kind, _, extra_domain in _SEARCH_SPECS:
                    if extra_kind == kind:
                        continue
                    tasks.append(
                        self._search_kind(
                            search_service,
                            kind=extra_kind,
                            topic=topic,
                            domain=extra_domain,
                            item_reason=item_reason,
                            max_results=1,
                        )
                    )

        groups = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[dict[str, str]] = []
        for group in groups:
            if isinstance(group, Exception):
                logger.warning("external feed search failed: %s", group)
                continue
            merged.extend(group)
        return self.dedupe_items(merged)

    async def _search_kind(
        self,
        search_service: WebSearchService,
        *,
        kind: ExternalResourceKind,
        topic: str,
        domain: str | None,
        item_reason: str,
        max_results: int = 2,
    ) -> list[dict[str, str]]:
        template = next(item[1] for item in _SEARCH_SPECS if item[0] == kind)
        query = template.format(topic=topic)
        try:
            result = await search_service.search(
                query=query,
                max_results=max(1, min(max_results, 3)),
                domain=domain,
            )
        except Exception:
            logger.exception("external feed search error kind=%s query=%s", kind, query)
            return []

        items: list[dict[str, str]] = []
        for raw in result.get("items") or []:
            normalized = self.normalize_item(
                kind=kind,
                topic=topic,
                title=str(raw.get("title") or "").strip(),
                url=str(raw.get("url") or "").strip(),
                snippet=str(raw.get("snippet") or "").strip(),
                reason=item_reason,
            )
            if normalized:
                items.append(normalized)
        return items

    @staticmethod
    def normalize_item(
        *,
        kind: ExternalResourceKind,
        topic: str,
        title: str,
        url: str,
        snippet: str,
        reason: str,
    ) -> dict[str, str] | None:
        cleaned_url = url.strip()
        if not cleaned_url or cleaned_url.startswith("https://example.com/mock"):
            return None
        if not title:
            title = cleaned_url
        domain = urlparse(cleaned_url).netloc.lower().removeprefix("www.")
        inferred_kind = ExternalResourceFeedService.infer_kind(cleaned_url, fallback=kind)
        return {
            "kind": inferred_kind,
            "topic": topic[:64],
            "title": title[:200],
            "url": cleaned_url,
            "snippet": snippet[:240],
            "source_domain": domain,
            "reason": reason,
        }

    @staticmethod
    def infer_kind(url: str, *, fallback: ExternalResourceKind) -> ExternalResourceKind:
        lowered = url.lower()
        if "bilibili.com" in lowered:
            return "video"
        if "github.com" in lowered:
            return "repo"
        if any(host in lowered for host in ("zhihu.com", "juejin.cn", "csdn.net", "medium.com", "dev.to")):
            return "blog"
        return fallback

    @staticmethod
    def dedupe_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
        seen: set[str] = set()
        unique: list[dict[str, str]] = []
        for item in items:
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            parsed = urlparse(url)
            key = f"{parsed.netloc.lower().removeprefix('www.')}{parsed.path.rstrip('/')}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique[:_MAX_FEED_ITEMS]

    @staticmethod
    def _cache_key(user_id: UUID, course_id: UUID, topics: list[str]) -> str:
        joined = "|".join(topics)
        digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]
        return f"external_feed:{user_id}:{course_id}:{digest}"

    async def _load_cache(self, key: str) -> dict[str, Any] | None:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            raw = await client.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
        finally:
            await client.aclose()

    async def _save_cache(self, key: str, payload: dict[str, Any]) -> None:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.set(key, json.dumps(payload, ensure_ascii=False), ex=_CACHE_TTL_SECONDS)
        finally:
            await client.aclose()
