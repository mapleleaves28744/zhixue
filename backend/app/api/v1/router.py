from fastapi import APIRouter, Request

from app.api.v1 import (
    admin,
    agents,
    auth,
    courses,
    diagnosis,
    evolution,
    materials,
    quizzes,
    resources,
    tutor,
    users,
    wiki,
)
from app.core.response import success_response


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "api_v1", "status": "ok"}, request=request)


router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(courses.router, prefix="/courses", tags=["courses"])
router.include_router(materials.router, prefix="/materials", tags=["materials"])
router.include_router(wiki.router, prefix="/wiki", tags=["wiki"])
router.include_router(tutor.router, prefix="/tutor", tags=["tutor"])
router.include_router(resources.router, prefix="/resources", tags=["resources"])
router.include_router(quizzes.router, prefix="/quizzes", tags=["quizzes"])
router.include_router(diagnosis.router, prefix="/diagnosis", tags=["diagnosis"])
router.include_router(evolution.router, prefix="/evolution", tags=["evolution"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
