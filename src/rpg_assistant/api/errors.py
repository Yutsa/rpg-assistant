from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ApiError(HTTPException):
    def __init__(self, status_code: int, detail: str, *, code: str | None = None) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def not_found(message: str) -> ApiError:
    return ApiError(404, message, code="not_found")


def bad_request(message: str) -> ApiError:
    return ApiError(400, message, code="bad_request")


def ambiguous_stat_block(candidates: list[dict]) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "Ambiguous stat block", "candidates": candidates},
    )


def pdf_not_found(message: str) -> ApiError:
    return ApiError(404, message, code="pdf_not_found")


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    payload: dict = {"error": exc.detail}
    if exc.code:
        payload["code"] = exc.code
    return JSONResponse(status_code=exc.status_code, content=payload)
