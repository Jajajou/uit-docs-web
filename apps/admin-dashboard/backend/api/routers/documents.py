"""Document routes aligned with the frontend DTO contracts."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import ApiContext, get_api_context, get_workspace_service, require_roles
from api.schemas import DocumentResponse, DocumentsResponse
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("", response_model=DocumentsResponse)
async def list_documents(
    search: Annotated[str | None, Query()] = None,
    lifecycle_status: Annotated[str | None, Query()] = None,
    visibility_scope: Annotated[str | None, Query()] = None,
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {
        "documents": service.list_documents(
            context.scenario,
            search=search,
            lifecycle_status=lifecycle_status,
            visibility_scope=visibility_scope,
        )
    }


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"document": service.get_document(doc_id, context.scenario)}


@router.post("/{doc_id}/archive", response_model=DocumentResponse)
async def archive_document(
    doc_id: str,
    context: ApiContext = Depends(require_roles("operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"document": service.archive_document(doc_id, context.role)}


@router.post("/{doc_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    doc_id: str,
    context: ApiContext = Depends(require_roles("operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"document": service.reindex_document(doc_id, context.role)}
