"""Shared API error types and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class ApiServiceError(Exception):
    """Normalized service-layer error used across the BFF."""

    status_code: int
    code: str
    message: str
    details: Any = field(default=None)


def build_error_response(request: Request, error: ApiServiceError) -> JSONResponse:
    """Return a normalized error envelope aligned with the frontend client."""

    request_id = getattr(request.state, "request_id", None)
    payload = {
        "error": {
            "code": error.code,
            "message": error.message,
            "status": error.status_code,
            "requestId": request_id,
            "details": error.details,
        }
    }
    response = JSONResponse(status_code=error.status_code, content=payload)
    if request_id:
        response.headers["x-request-id"] = request_id
    return response
