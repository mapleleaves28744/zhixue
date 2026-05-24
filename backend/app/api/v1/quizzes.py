from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.quiz import (
    QuizAttemptRead,
    QuizAttemptWithQuiz,
    QuizGenerateRequest,
    QuizRead,
    QuizSubmitRequest,
)
from app.services.quiz_service import QuizService

router = APIRouter()


@router.post("/generate")
async def generate_quizzes(
    payload: QuizGenerateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = QuizService(db)
    quizzes = await svc.generate_quizzes(
        user_id=current_user.id,
        course_id=payload.course_id,
        topic=payload.topic,
        count=payload.count,
        difficulty=payload.difficulty,
    )
    return success_response(
        {
            "items": [QuizRead.model_validate(q).model_dump(mode="json") for q in quizzes],
            "count": len(quizzes),
        },
        request=request,
    )


@router.get("")
async def list_quizzes(
    request: Request,
    course_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = QuizService(db)
    items, total = await svc.list_quizzes(
        user_id=current_user.id,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [QuizRead.model_validate(q).model_dump(mode="json") for q in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )


@router.post("/submit")
async def submit_answer(
    payload: QuizSubmitRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = QuizService(db)
    attempt = await svc.submit_answer(
        user_id=current_user.id,
        quiz_id=payload.quiz_id,
        user_answer=payload.user_answer,
        time_spent_seconds=payload.time_spent_seconds,
    )
    return success_response(QuizAttemptRead.model_validate(attempt).model_dump(mode="json"), request=request)


@router.get("/attempts")
async def list_attempts(
    request: Request,
    quiz_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = QuizService(db)
    items, total = await svc.get_attempts(
        user_id=current_user.id,
        quiz_id=quiz_id,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [QuizAttemptWithQuiz.model_validate(a).model_dump(mode="json") for a in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )


@router.get("/wrong-questions")
async def wrong_questions(
    request: Request,
    course_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = QuizService(db)
    items, total = await svc.get_wrong_questions(
        user_id=current_user.id,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [QuizAttemptWithQuiz.model_validate(a).model_dump(mode="json") for a in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )
