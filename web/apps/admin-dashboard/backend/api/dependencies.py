"""Shared dependencies for request context and services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query, Request

from api.config import settings
from api.errors import ApiServiceError
from api.schemas import Role
from api.services.ingestion_gateway import IngestionGateway
from api.services.workspace_service import InMemoryWorkspaceService
from api.services.workspace_store import SqlAlchemyWorkspaceStore, WorkspaceStateStore

INTERNAL_EMAIL_DOMAIN = "@gm.uit.edu.vn"
INTERNAL_ROLES: tuple[Role, ...] = ("teacher", "admin")
SESSION_COOKIE_NAME = "uit_web_session"
VALID_ROLES: tuple[Role, ...] = ("guest", "student", "teacher", "admin")
STORE: WorkspaceStateStore | None = None
SERVICE: InMemoryWorkspaceService | None = None
GATEWAY: IngestionGateway | None = None


@dataclass(slots=True)
class ApiContext:
    role: Role
    scenario: str
    request: Request
    session_token: str | None
    session: dict | None


def build_workspace_store(
    *,
    database_url: str | None = None,
    auto_seed: bool | None = None,
) -> WorkspaceStateStore:
    return SqlAlchemyWorkspaceStore(
        database_url=database_url or settings.WORKSPACE_DATABASE_URL,
        auto_seed=settings.WORKSPACE_AUTO_SEED if auto_seed is None else auto_seed,
    )


def reset_workspace_runtime(
    *,
    database_url: str | None = None,
    auto_seed: bool | None = None,
) -> InMemoryWorkspaceService:
    global STORE, SERVICE, GATEWAY
    if isinstance(STORE, SqlAlchemyWorkspaceStore):
        STORE.dispose()
    STORE = build_workspace_store(database_url=database_url, auto_seed=auto_seed)
    SERVICE = InMemoryWorkspaceService(store=STORE)
    GATEWAY = IngestionGateway()
    return SERVICE


def get_workspace_service() -> InMemoryWorkspaceService:
    if SERVICE is None:
        return reset_workspace_runtime()
    return SERVICE


def get_ingestion_gateway() -> IngestionGateway:
    global GATEWAY
    if GATEWAY is None:
        GATEWAY = IngestionGateway()
    return GATEWAY


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
    active_session = service.resolve_session(session_token, scenario)
    bootstrapped_role = active_session["user"]["role"] if active_session else service.resolve_session_role(session_token)
    demo_override_role = normalize_role(demo_role) if settings.ENABLE_DEMO_AUTH else None
    role = bootstrapped_role or demo_override_role or "guest"
    return ApiContext(role=role, scenario=scenario, request=request, session_token=session_token, session=active_session)


def ensure_role_access(context: ApiContext, allowed_roles: tuple[Role, ...], service: InMemoryWorkspaceService) -> None:
    if context.role not in allowed_roles:
        raise ApiServiceError(status_code=403, code="forbidden", message="Access denied for this route.")

    session = context.session or service.get_session(context.role, context.scenario)
    ensure_internal_session_compliance(context.role, session)


def require_roles(*allowed_roles: Role) -> Callable[..., ApiContext]:
    def dependency(
        context: ApiContext = Depends(get_api_context),
        service: InMemoryWorkspaceService = Depends(get_workspace_service),
    ) -> ApiContext:
        ensure_role_access(context, allowed_roles, service)
        return context

    return dependency


reset_workspace_runtime()
