"""Error envelope: every error response is ``{"error": {"code", "message", "details"}}``."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from ramus_api.shared.domain import BusinessError

logger = logging.getLogger(__name__)

INVALID_INPUT = "INVALID_INPUT"
INTERNAL_ERROR = "INTERNAL_ERROR"
INVALID_INPUT_MESSAGE = "입력 형식을 확인해 주세요."
INTERNAL_ERROR_MESSAGE = "요청을 처리하는 중에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요."
FALLBACK_HTTP_MESSAGE = "요청을 처리할 수 없습니다."

HTTP_ERRORS: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "요청 형식이 올바르지 않습니다."),
    401: ("UNAUTHORIZED", "로그인이 필요합니다."),
    403: ("FORBIDDEN", "이 작업을 할 권한이 없습니다."),
    404: ("NOT_FOUND", "요청한 대상을 찾을 수 없습니다."),
    405: ("METHOD_NOT_ALLOWED", "이 주소에서는 지원하지 않는 요청 방식입니다."),
    406: ("NOT_ACCEPTABLE", "요청한 응답 형식을 제공할 수 없습니다."),
    409: ("CONFLICT", "다른 변경과 충돌했습니다. 새로고침한 뒤 다시 시도해 주세요."),
    413: ("PAYLOAD_TOO_LARGE", "요청 내용이 너무 큽니다."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "지원하지 않는 요청 형식입니다."),
    429: ("TOO_MANY_REQUESTS", "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."),
    500: (INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE),
    503: ("SERVICE_UNAVAILABLE", "서비스를 잠시 사용할 수 없습니다. 잠시 후 다시 시도해 주세요."),
}


ErrorDetails = dict[str, Any] | list[Any] | None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: ErrorDetails


class ErrorResponse(BaseModel):
    error: ErrorBody


# App-wide OpenAPI responses: every 4xx/5xx body follows ErrorResponse.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "4XX": {"model": ErrorResponse, "description": "Client error"},
    "5XX": {"model": ErrorResponse, "description": "Server error"},
}


def error_json(
    status: int,
    code: str,
    message: str,
    details: ErrorDetails = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(body.model_dump(mode="json"), status_code=status, headers=headers)


def http_error_code(status: int) -> tuple[str, str]:
    return HTTP_ERRORS.get(status, (f"HTTP_{status}", FALLBACK_HTTP_MESSAGE))


def validation_details(error: RequestValidationError) -> list[dict[str, Any]]:
    """Location, type, and message only. The submitted ``input`` is never echoed back."""
    return [
        {"location": list(item.get("loc", ())), "type": item.get("type", ""), "message": item.get("msg", "")}
        for item in error.errors()
    ]


async def _business_error(_request: Request, exc: BusinessError) -> JSONResponse:
    return error_json(exc.status, exc.code, exc.message, exc.details)


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_json(422, INVALID_INPUT, INVALID_INPUT_MESSAGE, validation_details(exc))


async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = http_error_code(exc.status_code)
    return error_json(exc.status_code, code, message, headers=exc.headers)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return error_json(500, INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BusinessError, _business_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled_error)
