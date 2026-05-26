"""Proxy the LangGraph API used by the web frontend."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.config import settings

router = APIRouter()

REQUEST_HEADER_BLACKLIST = {"host", "content-length", "connection"}
RESPONSE_HEADER_BLACKLIST = {"content-length", "connection", "content-encoding", "transfer-encoding"}


def _target_base_url() -> str:
    return settings.LANGGRAPH_PUBLIC_URL or settings.LANGGRAPH_URL


def _proxy_request_headers(request: Request) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in REQUEST_HEADER_BLACKLIST
    }
    api_key = settings.LANGGRAPH_PUBLIC_API_KEY or settings.LANGGRAPH_API_KEY
    if api_key and "authorization" not in {key.lower() for key in headers}:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _proxy_response_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in RESPONSE_HEADER_BLACKLIST and key.lower() != "content-type"
    }


async def _stream_upstream_response(response: httpx.Response, client: httpx.AsyncClient) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await response.aclose()
        await client.aclose()


async def langgraph_proxy_impl(request: Request, path: str):
    target_base_url = _target_base_url()
    target_path = path[3:] if path.startswith("v1/") else path
    target_url = f"{target_base_url}/{target_path.lstrip('/')}".rstrip("/")
    if not target_path:
        target_url = target_base_url

    params = list(request.query_params.multi_items())
    body = await request.body()
    client = httpx.AsyncClient(timeout=settings.LANGGRAPH_TIMEOUT_SECONDS)

    try:
        upstream_response = await client.send(
            client.build_request(
                request.method,
                target_url,
                params=params,
                content=body,
                headers=_proxy_request_headers(request),
            ),
            stream=True,
        )
    except Exception as exc:
        await client.aclose()
        error = {"error": f"Proxy error: {exc}"}
        if "text/event-stream" in request.headers.get("accept", "").lower():

            async def error_stream() -> AsyncIterator[bytes]:
                yield f"data: {json.dumps(error)}\n\n".encode()

            return StreamingResponse(error_stream(), status_code=502, media_type="text/event-stream")
        return JSONResponse(error, status_code=502)

    # useStream hydrates thread state through JSON endpoints and only some calls are SSE.
    return StreamingResponse(
        _stream_upstream_response(upstream_response, client),
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
        headers=_proxy_response_headers(upstream_response),
    )


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def langgraph_proxy_wildcard(request: Request, path: str):
    return await langgraph_proxy_impl(request, path)


@router.api_route("/", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def langgraph_proxy_root(request: Request):
    return await langgraph_proxy_impl(request, "")
