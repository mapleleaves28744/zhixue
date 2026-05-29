from fastapi import APIRouter, Request

from app.api.v1 import (
    agents,
    auth,
    courses,
    diagnosis,
    evolution,
    knowledge,
    learning_records,
    learning_paths,
    materials,
    quizzes,
    recommendations,
    resources,
    student_memory,
    student_profile,
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
router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
router.include_router(learning_records.router, prefix="/learning-records", tags=["learning-records"])
router.include_router(learning_paths.router, prefix="/learning-paths", tags=["learning-paths"])
router.include_router(wiki.router, prefix="/wiki", tags=["wiki"])
router.include_router(tutor.router, prefix="/tutor", tags=["tutor"])
router.include_router(resources.router, prefix="/resources", tags=["resources"])
router.include_router(quizzes.router, prefix="/quizzes", tags=["quizzes"])
router.include_router(diagnosis.router, prefix="/diagnosis", tags=["diagnosis"])
router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
router.include_router(evolution.router, prefix="/evolution", tags=["evolution"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(student_profile.router, prefix="/student/profile", tags=["student-profile"])
router.include_router(student_memory.router, prefix="/student/memory", tags=["student-memory"])
