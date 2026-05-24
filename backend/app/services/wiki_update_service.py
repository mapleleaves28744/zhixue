from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm import ChatMessage, get_llm_provider
from app.models.wiki import WikiPage
from app.repositories.wiki_repository import WikiRepository
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class WikiUpdateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = WikiRepository(db)
        self.llm = get_llm_provider(db=db)
        self.prompts = PromptService(db)

    async def update_from_note(
        self,
        page_id: UUID,
        owner_id: UUID,
        note_content: str,
    ) -> WikiPage:
        page = await self.repo.get_by_id(page_id)
        if page is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Wiki 页面不存在",
                status_code=404,
            )
        if page.owner_id != owner_id:
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="无权编辑此 Wiki 页面",
                status_code=403,
            )
        if page.status == "archived":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="已归档的页面不可编辑",
                status_code=400,
            )

        # Use LLM to merge note into existing content
        merged_content = await self._merge_note(
            page.title,
            page.content,
            note_content,
            owner_id=owner_id,
            course_id=page.course_id,
        )
        new_version = page.current_version + 1

        await self.repo.update_page(
            page,
            content=merged_content,
            current_version=new_version,
        )
        await self.repo.create_version(
            page_id=page.id,
            version_number=new_version,
            title=page.title,
            content=merged_content,
            summary=page.summary,
            change_message="从笔记更新",
            created_by=owner_id,
        )

        # Create source for the note
        await self.repo.create_source(
            page_id=page.id,
            source_type="note",
            source_id=owner_id,
            source_title="学生笔记",
            quote_text=note_content[:200],
        )

        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def summarize_page(
        self, page_id: UUID, owner_id: UUID
    ) -> WikiPage:
        page = await self.repo.get_by_id(page_id)
        if page is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Wiki 页面不存在",
                status_code=404,
            )
        if page.owner_id != owner_id:
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="无权编辑此 Wiki 页面",
                status_code=403,
            )

        summary = await self._generate_summary(
            page.title,
            page.content,
            owner_id=owner_id,
            course_id=page.course_id,
        )
        new_version = page.current_version + 1

        await self.repo.update_page(
            page,
            summary=summary,
            current_version=new_version,
        )
        await self.repo.create_version(
            page_id=page.id,
            version_number=new_version,
            title=page.title,
            content=page.content,
            summary=summary,
            change_message="AI 生成摘要",
            created_by=owner_id,
        )

        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def _merge_note(
        self,
        title: str,
        existing_content: str,
        note: str,
        *,
        owner_id: UUID,
        course_id: UUID,
    ) -> str:
        rendered = await self.prompts.render_prompt(
            agent_name="WikiAgent",
            scene="wiki.merge_note",
            params={
                "title": title,
                "existing_content": existing_content,
                "note_content": note,
            },
        )
        try:
            response = await self.llm.chat(
                [ChatMessage(role="user", content=rendered.content)],
                temperature=0.5,
                max_tokens=4096,
                user_id=owner_id,
                course_id=course_id,
                prompt_version_id=rendered.prompt_version_id,
            )
            return response.content
        except Exception:
            logger.exception("LLM 合并笔记失败，使用追加方式")
            return (
                f"{existing_content}\n\n"
                f"---\n\n"
                f"## 补充笔记\n\n{note}"
            )

    async def _generate_summary(
        self,
        title: str,
        content: str,
        *,
        owner_id: UUID,
        course_id: UUID,
    ) -> str:
        rendered = await self.prompts.render_prompt(
            agent_name="WikiAgent",
            scene="wiki.summarize",
            params={
                "title": title,
                "content": content[:3000],
            },
        )
        try:
            response = await self.llm.chat(
                [ChatMessage(role="user", content=rendered.content)],
                temperature=0.3,
                max_tokens=512,
                user_id=owner_id,
                course_id=course_id,
                prompt_version_id=rendered.prompt_version_id,
            )
            return response.content
        except Exception:
            logger.exception("LLM 生成摘要失败，使用截断方式")
            plain = content.replace("#", "").replace("*", "").replace(">", "").strip()
            return plain[:200] + "..." if len(plain) > 200 else plain
