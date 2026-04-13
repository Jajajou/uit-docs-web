"""Job monitor routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import ApiContext, get_workspace_service, require_roles
from api.schemas import JobsResponse, RetryJobResponse
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("", response_model=JobsResponse)
async def list_jobs(
    status: Annotated[str | None, Query()] = None,
    job_type: Annotated[str | None, Query(alias="type")] = None,
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"jobs": service.list_jobs(context.scenario, status=status, job_type=job_type)}


@router.post("/{job_id}/retry", response_model=RetryJobResponse)
async def retry_job(
    job_id: str,
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"job": service.retry_job(job_id), "retry_accepted": True}
