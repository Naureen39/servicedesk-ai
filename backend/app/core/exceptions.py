"""RFC 7807 problem-details error handling."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx

PROBLEM_JSON = "application/problem+json"

_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    423: "Locked",
    429: "Too Many Requests",
    500: "Internal Server Error",
    501: "Not Implemented",
}


class AppError(HTTPException):
    """Base application error carrying an RFC 7807 `type` slug."""

    def __init__(self, status_code: int, detail: str, type_slug: str = "about:blank", **extra: object) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.type_slug = type_slug
        self.extra = extra


def _problem_response(status_code: int, detail: str, type_slug: str = "about:blank", **extra: object) -> JSONResponse:
    body = {
        "type": type_slug,
        "title": _TITLES.get(status_code, "Error"),
        "status": status_code,
        "detail": detail,
        "request_id": request_id_ctx.get(),
        **extra,
    }
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_JSON)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _problem_response(exc.status_code, str(exc.detail), exc.type_slug, **exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem_response(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Request validation failed",
            type_slug="https://meridian.example/problems/validation-error",
            errors=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return _problem_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")
