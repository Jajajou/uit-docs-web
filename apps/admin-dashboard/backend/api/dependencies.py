"""Shared dependencies for request context and services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query, Request

from api.errors import ApiServiceError
from api.schemas import Role
from api.services.workspace_service import InMemoryWorkspaceService

INTERNAL_EMAIL_DOMAIN = "@gm.uit.edu.vn"
INTERNAL_ROLES: tuple[Role, ...] = ("lecturer", "operator", "admin")
SESSION_COOKIE_NAME = "uit_web_session"
VALID_ROLES: tuple[Role, ...] = ("guest", "student", "lecturer", "operator", "admin")
SERVICE = InMemoryWorkspaceService()


@dataclass(slots=True)
class ApiContext:
    role: Role
    scenario: str
    request: Request


def get_workspace_service() -> InMemoryWorkspaceService:
    return SERVICE


def normalize_role(role: str | None) -> Role | None:
    if role in VALID_ROLES:
        return role
    return None


def is_internal_domain_compliant(role: Role, email: str) -> bool:
    return role not in INTERNAL_ROLES or email.lower().endswith(INTERNAL_EMAIL_DOMAIN)


def ensure_internal_session_compliance(role: Role, session: dict) -> None:
    email = str(session["user"]["email"]).lower()
    if not is_internal_domain_compliant(role, email):
        raise ApiServiceError(
            status_code=403,
            code="non_compliant_internal_email",
            message="The current session does not satisfy the institutional domain rule.",
        )


def get_api_context(
    request: Request,
    scenario: Annotated[str, Query()] = "happy",
    demo_role: Annotated[str | None, Header(alias="x-demo-role")] = None,
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> ApiContext:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    bootstrapped_role = service.resolve_session_role(session_token)
    role = bootstrapped_role or normalize_role(demo_role) or "guest"
    return ApiContext(role=role, scenario=scenario, request=request)


def ensure_role_access(context: ApiContext, allowed_roles: tuple[Role, ...], service: InMemoryWorkspaceService) -> None:
    if context.role not in allowed_roles:
        raise ApiServiceError(status_code=403, code="forbidden", message="Access denied for this route.")

    session = service.get_session(context.role, context.scenario)
    ensure_internal_session_compliance(context.role, session)


def require_roles(*allowed_roles: Role) -> Callable[..., ApiContext]:
    def dependency(
        context: ApiContext = Depends(get_api_context),
        service: InMemoryWorkspaceService = Depends(get_workspace_service),
    ) -> ApiContext:
        ensure_role_access(context, allowed_roles, service)
        return context

    return dependency
