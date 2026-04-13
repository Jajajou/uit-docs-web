"""Chat routes for /web contract alignment."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import ApiContext, get_api_context, get_workspace_service
from api.schemas import ChatResponseDto, ChatStreamRequest, ConversationsResponse
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("/sessions", response_model=ConversationsResponse)
async def list_sessions(
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {"conversations": service.list_conversations(context.scenario, context.role)}


@router.post("/stream", response_model=ChatResponseDto)
async def stream_chat(
    payload: ChatStreamRequest,
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return service.send_chat_message(payload.model_dump(), context.scenario, context.role)
