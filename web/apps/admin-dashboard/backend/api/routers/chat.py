"""Chat routes for /web contract alignment."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from api.dependencies import ApiContext, get_api_context, get_workspace_service
from api.schemas import ChatLiveSyncRequest, ChatResponseDto, ChatStreamRequest, ConversationsResponse
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


@router.get("/sessions", response_model=ConversationsResponse)
async def list_sessions(
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return {
        "conversations": service.list_conversations(
            context.scenario,
            context.role,
            context.session,
            context.session_token,
        )
    }


@router.post("/stream", response_model=ChatResponseDto)
async def stream_chat(
    payload: ChatStreamRequest,
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return service.send_chat_message(
        payload.model_dump(),
        context.scenario,
        context.role,
        context.session,
        context.session_token,
    )


@router.post("/live-sync", response_model=ChatResponseDto)
async def sync_live_chat(
    payload: ChatLiveSyncRequest,
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return service.persist_live_chat_message(
        payload.model_dump(),
        context.scenario,
        context.role,
        context.session,
        context.session_token,
    )


@router.delete("/sessions/{conversation_id}", status_code=204)
async def delete_session(
    conversation_id: str,
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> Response:
    service.delete_conversation(conversation_id, context.role, context.session, context.session_token)
    return Response(status_code=204)


@router.delete("/sessions", status_code=204)
async def clear_sessions(
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> Response:
    service.clear_conversations(context.role, context.session, context.session_token)
    return Response(status_code=204)
