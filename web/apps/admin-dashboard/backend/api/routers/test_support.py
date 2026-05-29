"""Test-only backend helpers for deterministic local and CI regression runs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from api.config import env_flag
from api.dependencies import SESSION_COOKIE_NAME, ensure_internal_session_compliance, get_workspace_service
from api.errors import ApiServiceError
from api.schemas import AuthBootstrapRequest, SessionDto
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter(include_in_schema=False)


def ensure_test_mode_enabled() -> None:
    if env_flag("TEST_MODE", "false"):
        return

    raise ApiServiceError(
        status_code=404,
        code="test_support_disabled",
        message="Test support routes are disabled in the current environment.",
    )


@router.post("/reset", status_code=204)
async def reset_test_state(
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> Response:
    ensure_test_mode_enabled()
    service.reset()

    response = Response(status_code=204)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return response


@router.post("/session", response_model=SessionDto)
async def issue_test_session(
    payload: AuthBootstrapRequest,
    response: Response,
    scenario: Annotated[str, Query()] = "happy",
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    ensure_test_mode_enabled()

    session = service.get_session(payload.role, scenario)
    ensure_internal_session_compliance(payload.role, session)
    session_token = service.issue_session_token(payload.role, auth_method="test_support_session", session=session)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return session
