import json
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from api.config import settings
from api.schemas import ChatStreamRequest

router = APIRouter()

@router.post("/chat")
async def student_chat(request: ChatStreamRequest):
    """
    Proxy student chat requests to the LangGraph RAG pipeline.
    Supports streaming responses via SSE.
    """
    async def stream_generator():
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Proxy to LangGraph
                async with client.stream(
                    "POST", 
                    f"{settings.LANGGRAPH_URL}/api/chat", 
                    json={"query": request.message}
                ) as response:
                    if response.status_code != 200:
                        yield f"data: {json.dumps({'error': f'LangGraph service error: {response.status_code}'})}\n\n"
                        return

                    async for chunk in response.aiter_text():
                        yield chunk
            except httpx.ConnectError:
                yield f"data: {json.dumps({'error': 'Cannot connect to LangGraph service. Ensure it is running on port 2024.'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Internal proxy error: {str(e)}'})}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
