"""Review queue routes and reviewer mutations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import ApiContext, get_workspace_service, require_roles
from api.schemas import ReviewDecisionRequest, ReviewsResponse, ReviewTaskResponse
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("", response_model=ReviewsResponse)
async def list_reviews(
    status: Annotated[str | None, Query()] = None,
    context: ApiContext = Depends(require_roles("operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"tasks": service.list_reviews(context.scenario, status=status)}


@router.post("/{review_id}/decision", response_model=ReviewTaskResponse)
async def apply_decision(
    review_id: str,
    payload: ReviewDecisionRequest,
    context: ApiContext = Depends(require_roles("operator", "admin")),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"task": service.apply_review_decision(review_id, payload.model_dump(exclude_none=True), context.role)}
