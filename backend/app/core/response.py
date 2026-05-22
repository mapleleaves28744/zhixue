from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.error_codes import ERROR_MESSAGES, ErrorCode


def generate_request_id() -> str:
    return f"req_{uuid4().hex}"


def get_request_id(request: Request | None = None) -> str:
    if request is None:
        return generate_request_id()
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return generate_request_id()


def success_response(
    data: Any = None,
    message: str = "success",
    request: Request | None = None,
) -> dict[str, Any]:
    return {
        "code": int(ErrorCode.SUCCESS),
        "message": message,
        "data": {} if data is None else data,
        "request_id": get_request_id(request),
    }


def page_response(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
    request: Request | None = None,
    message: str = "success",
) -> dict[str, Any]:
    return success_response(
        data={
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        message=message,
        request=request,
    )


def error_response(
    code: int,
    message: str | None = None,
    detail: Any = None,
    request: Request | None = None,
    status_code: int = 400,
) -> JSONResponse:
    content: dict[str, Any] = {
        "code": int(code),
        "message": message or ERROR_MESSAGES.get(code, "error"),
        "detail": detail,
        "request_id": get_request_id(request),
    }
    return JSONResponse(status_code=status_code, content=content)
