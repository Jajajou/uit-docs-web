"""Structured request-log middleware (R17.5, design C13, Property 14).

This module provides :class:`RequestLogMiddleware`, a single
``starlette.middleware.base.BaseHTTPMiddleware`` that emits exactly one
JSON log line per HTTP request after the response has been produced.
The log line carries the fields required by R17.5:

* ``timestamp`` — request completion instant in UTC ISO 8601 form.
* ``request_id`` — UUIDv4, taken from the inbound ``X-Request-Id``
  header when it parses as a valid UUIDv4, otherwise freshly generated.
* ``method`` — the HTTP method.
* ``path`` — the URL path (query string and request body are deliberately
  excluded to avoid logging PII).
* ``status`` — the integer HTTP status code of the response.
* ``duration_ms`` — measured wall-clock duration in milliseconds,
  clamped into ``[0, 600000]`` so anomalous monotonic-clock readings
  cannot violate Property 14.
* ``user_id_hash`` — SHA-256 hex digest of the authenticated subject
  claim taken from ``request.state.user_id``; empty string when the
  request is unauthenticated.

The middleware also propagates the resolved ``request_id`` to the
client by setting the response ``X-Request-Id`` header so downstream
operators can correlate log lines with API responses.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("admin_backend.request_log")

REQUEST_ID_HEADER = "X-Request-Id"
DURATION_MS_MAX = 600_000


def _coerce_request_id(raw: str | None) -> str:
    """Return ``raw`` unchanged when it parses as a UUIDv4, else a new one."""

    if raw is None:
        return str(uuid.uuid4())
    candidate = raw.strip()
    if not candidate:
        return str(uuid.uuid4())
    try:
        parsed = uuid.UUID(candidate)
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid4())
    if parsed.version != 4:
        return str(uuid.uuid4())
    # Normalise to canonical lower-case form.
    return str(parsed)


def _hash_user_id(user_id: Any) -> str:
    """Return the SHA-256 hex digest of ``user_id`` or ``""`` when absent."""

    if user_id is None:
        return ""
    if not isinstance(user_id, str):
        user_id = str(user_id)
    if not user_id:
        return ""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def _utc_iso8601(now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(tz=timezone.utc)
    # ``datetime.isoformat`` on a tz-aware UTC value produces the
    # ``+00:00`` suffix; replace it with ``Z`` for the canonical
    # ISO 8601 UTC representation.
    text = now.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    return text


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Emit exactly one structured JSON log line per HTTP request."""

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start = time.monotonic()

        request_id = _coerce_request_id(request.headers.get(REQUEST_ID_HEADER))
        # Expose the resolved id to downstream handlers so they can
        # correlate their own log entries with this middleware.
        request.state.request_id = request_id

        response = await call_next(request)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        if elapsed_ms < 0:
            elapsed_ms = 0
        elif elapsed_ms > DURATION_MS_MAX:
            elapsed_ms = DURATION_MS_MAX

        user_id = getattr(request.state, "user_id", None)
        user_id_hash = _hash_user_id(user_id)

        record = {
            "timestamp": _utc_iso8601(),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": int(response.status_code),
            "duration_ms": elapsed_ms,
            "user_id_hash": user_id_hash,
        }

        # Single log call, single JSON line: the unit tests rely on this
        # to satisfy Property 14 (exactly one log line per request).
        logger.info(json.dumps(record, separators=(",", ":"), ensure_ascii=False))

        response.headers[REQUEST_ID_HEADER] = request_id
        return response


__all__ = ["RequestLogMiddleware", "REQUEST_ID_HEADER", "DURATION_MS_MAX"]
