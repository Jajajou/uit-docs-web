"""Property-based test for the structured request-log middleware.

Property 14: Structured Request Log.

**Validates: Requirements 17.5**

For any HTTP request handled by ``Admin_Backend``,
:class:`app.middleware.request_log.RequestLogMiddleware` SHALL emit
exactly one log line, in valid JSON, containing all of the fields
``timestamp``, ``request_id``, ``method``, ``path``, ``status``,
``duration_ms``, ``user_id_hash``, with ``timestamp`` parseable as
ISO 8601 UTC, ``request_id`` a non-empty UUIDv4 string, ``status`` an
integer in ``[100, 599]``, ``duration_ms`` an integer in
``[0, 600000]``, and ``user_id_hash`` empty *iff* the request is
unauthenticated (``request.state.user_id`` is absent or empty).

Strategy:

* ``method``: ``sampled_from`` over the five HTTP verbs the admin
  dashboard exposes.
* ``path``: ``from_regex(r"^/[a-z0-9/\\-_]{0,64}$", fullmatch=True)`` -
  generates safe URL paths under the design's whitelist, including the
  root ``/``.
* ``status``: ``integers(min_value=100, max_value=599)``.
* ``user_id``: ``one_of(none(), text(min_size=0, max_size=64))`` to
  cover both unauthenticated and authenticated requests, including the
  empty-string boundary that must still hash to ``""``.

Each Hypothesis example mounts a single-route Starlette app, sends a
synthetic request through the in-process ``TestClient``, captures the
log output via the ``caplog`` fixture, and asserts the property above.
``max_examples=100`` per the design's testing strategy table T1 and
sub-task 10.4.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.request_log import (
    DURATION_MS_MAX,
    RequestLogMiddleware,
)

LOGGER_NAME = "admin_backend.request_log"
HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")

# UUIDv4 canonical form (lower-case hex, version nibble 4, variant 8/9/a/b).
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _build_app(*, status_code: int, user_id: str | None) -> Starlette:
    """Return a Starlette app whose only route returns ``status_code``.

    The handler optionally stamps ``request.state.user_id`` so the
    middleware exercises the SHA-256 branch of Property 14.
    """

    async def handler(request: Request) -> PlainTextResponse:
        if user_id is not None:
            request.state.user_id = user_id
        return PlainTextResponse("", status_code=status_code)

    app = Starlette(
        routes=[
            Route(
                "/{full_path:path}",
                handler,
                methods=list(HTTP_METHODS),
            )
        ]
    )
    app.add_middleware(RequestLogMiddleware)
    return app


@settings(
    max_examples=100,
    # ``caplog`` is function-scoped and is reset explicitly at the top
    # of the test body, so suppress Hypothesis' default warning.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    method=st.sampled_from(HTTP_METHODS),
    path=st.from_regex(r"^/[a-z0-9/\-_]{0,64}$", fullmatch=True),
    status=st.integers(min_value=100, max_value=599),
    user_id=st.one_of(st.none(), st.text(min_size=0, max_size=64)),
)
def test_property_14_structured_request_log(
    caplog: pytest.LogCaptureFixture,
    method: str,
    path: str,
    status: int,
    user_id: str | None,
) -> None:
    """Property 14: every request emits exactly one well-formed JSON log line."""

    caplog.clear()
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    app = _build_app(status_code=status, user_id=user_id)
    with TestClient(app, follow_redirects=False) as client:
        response = client.request(method, path)

    # Sanity: the synthetic handler returned the drawn status.
    assert response.status_code == status

    # --- Property 14, clause 1: exactly one log line is emitted ----------
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == LOGGER_NAME
    ]
    assert len(lines) == 1, f"expected exactly one log line, got: {lines!r}"

    # --- Property 14, clause 2: it parses as JSON ------------------------
    record: dict[str, Any] = json.loads(lines[0])
    assert isinstance(record, dict), f"log line is not a JSON object: {record!r}"

    # --- Property 14, clause 3: all seven required fields are present ----
    required = (
        "timestamp",
        "request_id",
        "method",
        "path",
        "status",
        "duration_ms",
        "user_id_hash",
    )
    for key in required:
        assert key in record, f"missing field {key!r} in {record!r}"

    # --- Property 14, clause 4: types and ranges -------------------------
    # timestamp: ISO 8601 UTC string.
    assert isinstance(record["timestamp"], str)
    ts: str = record["timestamp"]
    parsable = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    parsed_ts = datetime.fromisoformat(parsable)  # raises if not ISO 8601
    # The middleware emits UTC; round-tripped value must carry tzinfo.
    assert parsed_ts.tzinfo is not None
    assert parsed_ts.utcoffset() is not None
    assert parsed_ts.utcoffset().total_seconds() == 0

    # request_id: non-empty UUIDv4 string.
    assert isinstance(record["request_id"], str)
    assert record["request_id"] != ""
    assert _UUID4_RE.match(record["request_id"]), (
        f"request_id is not a UUIDv4: {record['request_id']!r}"
    )

    # method: matches what the client sent.
    assert isinstance(record["method"], str)
    assert record["method"] == method

    # path: matches the request URL path.
    assert isinstance(record["path"], str)
    assert record["path"] == path

    # status: integer in [100, 599] equal to what the handler returned.
    # ``bool`` is a subclass of ``int`` in Python; rule it out explicitly.
    assert isinstance(record["status"], int) and not isinstance(
        record["status"], bool
    )
    assert record["status"] == status
    assert 100 <= record["status"] <= 599

    # duration_ms: integer clamped into [0, 600000].
    assert isinstance(record["duration_ms"], int) and not isinstance(
        record["duration_ms"], bool
    )
    assert 0 <= record["duration_ms"] <= DURATION_MS_MAX

    # --- Property 14, clause 5: user_id_hash empty iff unauthenticated ---
    assert isinstance(record["user_id_hash"], str)
    if user_id is None or user_id == "":
        assert record["user_id_hash"] == "", (
            "user_id_hash must be empty when the request is unauthenticated"
        )
    else:
        expected = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        assert record["user_id_hash"] == expected
        assert len(record["user_id_hash"]) == 64
