"""Admin console routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import ApiContext, get_workspace_service, require_roles
from api.schemas import (
    AdminUserPatchRequest,
    AdminUserResponse,
    AdminUsersResponse,
    AuditLogsResponse,
    RolePoliciesResponse,
    SystemSettingPatchRequest,
    SystemSettingResponse,
    SystemSettingsResponse,
)
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("/users", response_model=AdminUsersResponse)
async def list_admin_users(
    role: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    compliance: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {
        "users": service.list_admin_users(
            context.scenario,
            role_filter=role,
            status_filter=status,
            compliance=compliance,
            search=search,
        )
    }


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def patch_admin_user(
    user_id: str,
    payload: AdminUserPatchRequest,
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"user": service.update_admin_user(user_id, payload.model_dump(exclude_none=True))}


@router.get("/roles", response_model=RolePoliciesResponse)
async def list_role_policies(
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"roles": service.list_role_policies(context.scenario)}


@router.get("/settings", response_model=SystemSettingsResponse)
async def list_system_settings(
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"settings": service.list_system_settings(context.scenario)}


@router.patch("/settings/{key}", response_model=SystemSettingResponse)
async def patch_system_setting(
    key: str,
    payload: SystemSettingPatchRequest,
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"setting": service.update_system_setting(key, payload.value)}


@router.get("/audit-logs", response_model=AuditLogsResponse)
async def list_audit_logs(
    actor_role: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    target_type: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {
        "logs": service.list_audit_logs(
            context.scenario,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            search=search,
        )
    }
