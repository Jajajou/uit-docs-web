"""Upload routes aligned with the frontend upload contract."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import ApiContext, get_workspace_service, require_roles
from api.schemas import SubmissionResponse, UploadSubmissionRequest
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.post("/file", response_model=SubmissionResponse, status_code=202)
async def upload_file(
    payload: UploadSubmissionRequest,
    context: ApiContext = Depends(require_roles("lecturer", "operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"submission": service.create_submission(payload.model_dump(exclude_none=True), context.scenario, context.role)}


@router.post("/text", response_model=SubmissionResponse, status_code=202)
async def upload_text(
    payload: UploadSubmissionRequest,
    context: ApiContext = Depends(require_roles("lecturer", "operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"submission": service.create_submission(payload.model_dump(exclude_none=True), context.scenario, context.role)}


@router.post("/url", response_model=SubmissionResponse, status_code=202)
async def upload_url(
    payload: UploadSubmissionRequest,
    context: ApiContext = Depends(require_roles("lecturer", "operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"submission": service.create_submission(payload.model_dump(exclude_none=True), context.scenario, context.role)}


@router.post("/scan")
async def trigger_scan(
    context: ApiContext = Depends(require_roles("operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"job": service.retry_job("job-002"), "scan_triggered": True}
