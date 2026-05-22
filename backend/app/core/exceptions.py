from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import (
    ERROR_MESSAGES,
    HTTP_STATUS_BY_CODE,
    ErrorCode,
)
from app.core.response import error_response


class BusinessException(Exception):
    def __init__(
        self,
        code: int = ErrorCode.BUSINESS_VALIDATION_ERROR,
        message: str | None = None,
        detail: Any = None,
        status_code: int | None = None,
    ) -> None:
        self.code = int(code)
        self.message = message or ERROR_MESSAGES.get(code, "业务异常")
        self.detail = detail
        self.status_code = status_code or HTTP_STATUS_BY_CODE.get(code, 400)
        super().__init__(self.message)


async def business_exception_handler(
    request: Request,
    exc: BusinessException,
):
    return error_response(
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
        request=request,
        status_code=exc.status_code,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return error_response(
        code=ErrorCode.REQUEST_BODY_ERROR,
        message=ERROR_MESSAGES[ErrorCode.REQUEST_BODY_ERROR],
        detail=exc.errors(),
        request=request,
        status_code=400,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    code = _map_http_status_to_error_code(exc.status_code)
    return error_response(
        code=code,
        message=ERROR_MESSAGES.get(code),
        detail=exc.detail,
        request=request,
        status_code=exc.status_code,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    return error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message=ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR],
        detail="internal server error",
        request=request,
        status_code=500,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


def _map_http_status_to_error_code(status_code: int) -> int:
    if status_code == 401:
        return int(ErrorCode.UNAUTHORIZED)
    if status_code == 403:
        return int(ErrorCode.FORBIDDEN)
    if status_code == 404:
        return int(ErrorCode.NOT_FOUND)
    if status_code == 409:
        return int(ErrorCode.CONFLICT)
    if status_code == 422:
        return int(ErrorCode.BUSINESS_VALIDATION_ERROR)
    if status_code == 429:
        return int(ErrorCode.TOO_MANY_REQUESTS)
    if 400 <= status_code < 500:
        return int(ErrorCode.PARAM_ERROR)
    return int(ErrorCode.INTERNAL_ERROR)
