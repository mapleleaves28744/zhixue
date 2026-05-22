from fastapi import APIRouter, Request

from app.core.response import success_response


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "courses", "status": "ok"}, request=request)
