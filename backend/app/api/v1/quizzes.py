from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_student
from app.core.response import page_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.quiz import QuizGenerateRequest, QuizSubmitRequest
from app.services.quiz_service import QuizService

router = APIRouter()


@router.post("/generate")
async def generate_quiz(
    payload: QuizGenerateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await QuizService(db).generate_quiz(
        payload=payload,
        current_user=current_user,
    )
    return success_response(data.model_dump(mode="json"), request=request)


@router.get("")
async def list_quizzes(
    request: Request,
    course_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items, total = await QuizService(db).list_quizzes(
        current_user=current_user,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return page_response(
        items=[item.model_dump(mode="json") for item in items],
        total=total,
        page=page,
        page_size=page_size,
        request=request,
    )


@router.get("/mistakes")
async def list_mistakes(
    request: Request,
    course_id: UUID | None = Query(default=None),
    knowledge_id: UUID | None = Query(default=None),
    status: str | None = Query(default="unresolved"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items, total = await QuizService(db).list_mistakes(
        current_user=current_user,
        course_id=course_id,
        knowledge_id=knowledge_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return page_response(
        items=[item.model_dump(mode="json") for item in items],
        total=total,
        page=page,
        page_size=page_size,
        request=request,
    )


@router.get("/{quiz_id}")
async def get_quiz(
    quiz_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await QuizService(db).get_quiz(
        quiz_id=quiz_id,
        current_user=current_user,
    )
    return success_response(data.model_dump(mode="json"), request=request)


@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: UUID,
    payload: QuizSubmitRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await QuizService(db).submit_answers(
        quiz_id=quiz_id,
        payload=payload,
        current_user=current_user,
    )
    return success_response(data.model_dump(mode="json"), request=request)
