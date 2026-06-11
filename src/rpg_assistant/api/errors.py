from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


def not_found(resource: str, identifier: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown {resource}: {identifier}",
    )


def ambiguous_stat_block(candidates: list[dict[str, Any]]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"error": "Ambiguous stat block", "candidates": candidates},
    )


def pdf_not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=message,
    )


def pdf_unavailable(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=message,
    )
