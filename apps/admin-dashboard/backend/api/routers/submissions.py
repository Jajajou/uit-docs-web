"""Submission routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import ApiContext, get_workspace_service, require_roles
from api.schemas import SubmissionResponse, SubmissionsResponse
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("", response_model=SubmissionsResponse)
async def list_submissions(
    lifecycle_status: Annotated[str | None, Query()] = None,
    context: ApiContext = Depends(require_roles("lecturer", "operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"submissions": service.list_submissions(context.scenario, lifecycle_status=lifecycle_status)}


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: str,
    context: ApiContext = Depends(require_roles("lecturer", "operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"submission": service.get_submission(submission_id, context.scenario)}
