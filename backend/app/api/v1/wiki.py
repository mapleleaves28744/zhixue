from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_student
from app.core.response import page_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.wiki import (
    GenerateFromMaterialRequest,
    UpdateFromNoteRequest,
    WikiPageCreate,
    WikiPageUpdate,
)
from app.services.wiki_generate_service import WikiGenerateService
from app.services.wiki_service import WikiService
from app.services.wiki_update_service import WikiUpdateService

router = APIRouter()


@router.get("/pages")
async def list_wiki_pages(
    request: Request,
    course_id: UUID = Query(...),
    status: str | None = Query(default="active"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    items, total = await svc.list_pages(
        owner_id=current_user.id,
        course_id=course_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return page_response(
        items=[
            {
                "id": str(p.id),
                "course_id": str(p.course_id),
                "title": p.title,
                "slug": p.slug,
                "summary": p.summary,
                "status": p.status,
                "current_version": p.current_version,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        request=request,
    )


@router.get("/pages/{page_id}")
async def get_wiki_page(
    page_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    page = await svc.get_page(page_id, current_user.id)
    return success_response(
        {
            "id": str(page.id),
            "course_id": str(page.course_id),
            "owner_id": str(page.owner_id),
            "title": page.title,
            "slug": page.slug,
            "summary": page.summary,
            "content": page.content,
            "status": page.status,
            "current_version": page.current_version,
            "extra_meta": page.extra_meta,
            "created_at": page.created_at.isoformat(),
            "updated_at": page.updated_at.isoformat(),
            "sources": [
                {
                    "id": str(s.id),
                    "source_type": s.source_type,
                    "source_id": str(s.source_id),
                    "source_title": s.source_title,
                    "quote_text": s.quote_text,
                }
                for s in (page.sources or [])
            ],
        },
        request=request,
    )


@router.post("/pages")
async def create_wiki_page(
    body: WikiPageCreate,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    page = await svc.create_page(
        owner_id=current_user.id,
        course_id=body.course_id,
        title=body.title,
        content=body.content,
        summary=body.summary,
    )
    return success_response(
        {
            "id": str(page.id),
            "title": page.title,
            "slug": page.slug,
            "current_version": page.current_version,
        },
        request=request,
    )


@router.put("/pages/{page_id}")
async def update_wiki_page(
    page_id: UUID,
    body: WikiPageUpdate,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    page = await svc.update_page(
        page_id=page_id,
        owner_id=current_user.id,
        title=body.title,
        content=body.content,
        summary=body.summary,
        change_message=body.change_message,
    )
    return success_response(
        {
            "id": str(page.id),
            "title": page.title,
            "current_version": page.current_version,
            "updated_at": page.updated_at.isoformat(),
        },
        request=request,
    )


@router.delete("/pages/{page_id}")
async def archive_wiki_page(
    page_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    await svc.archive_page(page_id, current_user.id)
    return success_response({"archived": True}, request=request)


@router.get("/pages/{page_id}/versions")
async def list_wiki_versions(
    page_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    versions = await svc.list_versions(page_id, current_user.id)
    return success_response(
        [
            {
                "id": str(v.id),
                "page_id": str(v.page_id),
                "version_number": v.version_number,
                "title": v.title,
                "content": v.content,
                "summary": v.summary,
                "change_message": v.change_message,
                "created_by": str(v.created_by),
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
        request=request,
    )


@router.get("/pages/{page_id}/versions/{version_number}")
async def get_wiki_version(
    page_id: UUID,
    version_number: int,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    await svc.get_page(page_id, current_user.id)
    from app.repositories.wiki_repository import WikiRepository

    repo = WikiRepository(db)
    version = await repo.get_version(page_id, version_number)
    if version is None:
        from app.core.error_codes import ErrorCode
        from app.core.exceptions import BusinessException

        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail=f"版本 v{version_number} 不存在",
            status_code=404,
        )
    return success_response(
        {
            "id": str(version.id),
            "page_id": str(version.page_id),
            "version_number": version.version_number,
            "title": version.title,
            "content": version.content,
            "summary": version.summary,
            "change_message": version.change_message,
            "created_by": str(version.created_by),
            "created_at": version.created_at.isoformat(),
        },
        request=request,
    )


@router.post("/pages/{page_id}/rollback/{version_number}")
async def rollback_wiki_page(
    page_id: UUID,
    version_number: int,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiService(db)
    page = await svc.rollback(page_id, current_user.id, version_number)
    return success_response(
        {
            "id": str(page.id),
            "title": page.title,
            "current_version": page.current_version,
            "updated_at": page.updated_at.isoformat(),
        },
        request=request,
    )


# ---- Generate & AI endpoints ----


@router.post("/pages/generate-from-material")
async def generate_wiki_from_material(
    body: GenerateFromMaterialRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiGenerateService(db)
    pages = await svc.generate_from_material(
        course_id=body.course_id,
        material_id=body.material_id,
        owner_id=current_user.id,
    )
    return success_response(
        {
            "generated_count": len(pages),
            "pages": [
                {
                    "id": str(p.id),
                    "title": p.title,
                    "slug": p.slug,
                    "current_version": p.current_version,
                }
                for p in pages
            ],
        },
        request=request,
    )


@router.post("/pages/update-from-note")
async def update_wiki_from_note(
    body: UpdateFromNoteRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiUpdateService(db)
    page = await svc.update_from_note(
        page_id=body.page_id,
        owner_id=current_user.id,
        note_content=body.note_content,
    )
    return success_response(
        {
            "id": str(page.id),
            "title": page.title,
            "current_version": page.current_version,
            "updated_at": page.updated_at.isoformat(),
        },
        request=request,
    )


@router.post("/pages/{page_id}/summarize")
async def summarize_wiki_page(
    page_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = WikiUpdateService(db)
    page = await svc.summarize_page(page_id, current_user.id)
    return success_response(
        {
            "id": str(page.id),
            "title": page.title,
            "summary": page.summary,
            "current_version": page.current_version,
            "updated_at": page.updated_at.isoformat(),
        },
        request=request,
    )


# ---- Graph endpoints ----


@router.get("/graph")
async def get_wiki_graph(
    request: Request,
    course_id: UUID = Query(...),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from app.repositories.wiki_repository import WikiRepository

    repo = WikiRepository(db)
    pages, _ = await repo.list_by_owner(
        owner_id=current_user.id,
        course_id=course_id,
        status="active",
        page=1,
        page_size=200,
    )

    all_links: list[dict[str, object]] = []
    for p in pages:
        links = await repo.list_links(p.id)
        for link in links:
            all_links.append(
                {
                    "id": str(link.id),
                    "source_page_id": str(link.source_page_id),
                    "target_page_id": str(link.target_page_id),
                    "relation_type": link.relation_type,
                }
            )

    # Deduplicate links
    seen: set[str] = set()
    unique_links: list[dict[str, object]] = []
    for link in all_links:
        key = f"{link['source_page_id']}-{link['target_page_id']}-{link['relation_type']}"
        if key not in seen:
            seen.add(key)
            unique_links.append(link)

    return success_response(
        {
            "nodes": [
                {
                    "id": str(p.id),
                    "title": p.title,
                    "summary": p.summary,
                    "current_version": p.current_version,
                }
                for p in pages
            ],
            "links": unique_links,
        },
        request=request,
    )
