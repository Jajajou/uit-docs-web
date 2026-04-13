"""Upload routes — supports both JSON contract and multipart/form-data.

When LIVE_INGESTION_MODE is enabled, files are staged locally via the
IngestionGateway and forwarded to LightRAG.  When disabled (default),
the existing mock submission/job/review contract is preserved.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.dependencies import ApiContext, get_ingestion_gateway, get_workspace_service, require_roles
from api.errors import ApiServiceError
from api.schemas import SubmissionResponse, UploadSubmissionRequest
from api.services.ingestion_gateway import IngestionGateway
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.post("/file", response_model=SubmissionResponse, status_code=202)
async def upload_file(
    payload: UploadSubmissionRequest,
    context: ApiContext = Depends(require_roles("teacher", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
) -> dict:
    """Accept a JSON file-upload contract (existing frontend flow)."""
    return {"submission": service.create_submission(payload.model_dump(exclude_none=True), context.scenario, context.role)}


@router.post("/file/multipart", response_model=SubmissionResponse, status_code=202)
async def upload_file_multipart(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    visibility_scope: str | None = Form(None),
    tags: str | None = Form(None),
    notes: str | None = Form(None),
    issuing_unit: str | None = Form(None),
    context: ApiContext = Depends(require_roles("teacher", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
) -> dict:
    """Accept a real file upload via multipart/form-data (live ingestion flow)."""
    file_content = await file.read()
    submission: dict | None = None
    staged_path: str | None = None
    effective_payload = {
        "title": title or file.filename or "Untitled",
        "fileName": file.filename,
        "sourceType": "file",
        "visibilityScope": visibility_scope or "internal",
        "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
        "notes": notes or "",
        "issuingUnit": issuing_unit or "",
    }

    try:
        submission = service.create_submission(effective_payload, context.scenario, context.role)

        if gateway.live:
            staged_path = gateway.stage_file(file.filename or "upload.bin", file_content)
            ingest_result = gateway.ingest_file(staged_path, metadata={"title": effective_payload.get("title")})
            if ingest_result.get("error"):
                raise ApiServiceError(
                    status_code=502,
                    code="ingestion_failed",
                    message="Live ingestion failed while forwarding the uploaded file.",
                    details={"provider": "lightrag", "response": ingest_result["error"]},
                )
            submission = service.mark_submission_ingestion_started(submission["id"], ingest_result)

        return {"submission": submission}
    except ApiServiceError as error:
        if submission is not None:
            service.mark_submission_ingestion_failed(submission["id"], error.message)
        raise
    except Exception as exc:
        if submission is not None:
            service.mark_submission_ingestion_failed(submission["id"], f"Live ingestion failed: {exc}")
        raise ApiServiceError(
            status_code=502,
            code="ingestion_failed",
            message="Live ingestion failed while forwarding the uploaded file.",
            details={"provider": "lightrag"},
        ) from exc
    finally:
        if staged_path:
            gateway.cleanup_staged_file(staged_path)


@router.post("/text", response_model=SubmissionResponse, status_code=202)
async def upload_text(
    payload: UploadSubmissionRequest,
    context: ApiContext = Depends(require_roles("teacher", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
) -> dict:
    submission = service.create_submission(payload.model_dump(exclude_none=True), context.scenario, context.role)

    if gateway.live and payload.content:
        try:
            ingest_result = gateway.ingest_text(payload.content, source=payload.title)
            if ingest_result.get("error"):
                raise ApiServiceError(
                    status_code=502,
                    code="ingestion_failed",
                    message="Live ingestion failed while forwarding the pasted text.",
                    details={"provider": "lightrag", "response": ingest_result["error"]},
                )
            submission = service.mark_submission_ingestion_started(submission["id"], ingest_result)
        except ApiServiceError as error:
            service.mark_submission_ingestion_failed(submission["id"], error.message)
            raise
        except Exception as exc:
            service.mark_submission_ingestion_failed(submission["id"], f"Live ingestion failed: {exc}")
            raise ApiServiceError(
                status_code=502,
                code="ingestion_failed",
                message="Live ingestion failed while forwarding the pasted text.",
                details={"provider": "lightrag"},
            ) from exc

    return {"submission": submission}


@router.post("/url", response_model=SubmissionResponse, status_code=202)
async def upload_url(
    payload: UploadSubmissionRequest,
    context: ApiContext = Depends(require_roles("teacher", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
) -> dict:
    submission = service.create_submission(payload.model_dump(exclude_none=True), context.scenario, context.role)
    return {"submission": submission}


@router.post("/scan")
async def trigger_scan(
    context: ApiContext = Depends(require_roles("admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
) -> dict:
    job = service.retry_job("job-002")
    scan_result = gateway.trigger_reindex() if gateway.live else {}
    return {"job": job, "scan_triggered": True, **scan_result}
