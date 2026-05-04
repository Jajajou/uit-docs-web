import json
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from api.config import settings

router = APIRouter()

async def langgraph_proxy_impl(request: Request, path: str):
    """
    Core implementation of the wildcard proxy.
    """
    # LangGraph SDK often adds /v1/ prefix, but local server might not use it
    target_path = path
    if target_path.startswith("v1/"):
        target_path = target_path.replace("v1/", "", 1)
        
    url = f"{settings.LANGGRAPH_URL}/{target_path}"
    
    # Forward query params
    params = dict(request.query_params)
    
    # Get body for POST/PUT
    body = await request.body()
    
    # Forward headers, but remove host and content-length to avoid proxy conflicts
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "connection")}
    
    async def stream_generator():
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                # Stream the request to LangGraph server
                async with client.stream(
                    request.method,
                    url,
                    params=params,
                    content=body,
                    headers=headers,
                ) as response:
                    # Stream the response back to the frontend
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                # Return a formatted SSE error
                error_data = json.dumps({'error': f'Proxy error: {str(e)}'})
                yield f"data: {error_data}\n\n".encode()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream"
    )

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def langgraph_proxy_wildcard(request: Request, path: str):
    return await langgraph_proxy_impl(request, path)

@router.api_route("/", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def langgraph_proxy_root(request: Request):
    return await langgraph_proxy_impl(request, "")
