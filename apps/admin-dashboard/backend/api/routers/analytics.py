"""Analytics routes backed by the in-memory workspace service."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_workspace_service
from api.schemas import GraphStatsResponse, HealthResponse, OverviewStats, PipelineStatus
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("/overview", response_model=OverviewStats)
async def get_overview(service: InMemoryWorkspaceService = Depends(get_workspace_service)) -> dict:
    return service.get_overview()


@router.get("/pipeline", response_model=PipelineStatus)
async def get_pipeline_status(service: InMemoryWorkspaceService = Depends(get_workspace_service)) -> dict:
    return service.get_pipeline_status()


@router.get("/graph-stats", response_model=GraphStatsResponse)
async def get_graph_stats(service: InMemoryWorkspaceService = Depends(get_workspace_service)) -> dict:
    return service.get_graph_stats()


@router.get("/health", response_model=HealthResponse)
async def check_all_health(service: InMemoryWorkspaceService = Depends(get_workspace_service)) -> dict:
    return service.get_health()
