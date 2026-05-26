"""Unit tests for :mod:`app.middleware.request_log`.

Covers the deterministic, non-property assertions for R17.5 / design
C13. The Hypothesis property test (Property 14, sub-task 10.4) lives in
a separate module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.request_log import (
    DURATION_MS_MAX,
    REQUEST_ID_HEADER,
    RequestLogMiddleware,
    _coerce_request_id,
    _hash_user_id,
)

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(*, set_user_id: str | None = None) -> Starlette:
    async def ok(request: Request) -> PlainTextResponse:
        if set_user_id is not None:
            request.state.user_id = set_user_id
        return PlainTextResponse("ok")

    async def echo(request: Request) -> JSONResponse:
        if set_user_id is not None:
            request.state.user_id = set_user_id
        return JSONResponse({"path": request.url.path})

    async def teapot(request: Request) -> PlainTextResponse:
        if set_user_id is not None:
            request.state.user_id = set_user_id
        return PlainTextResponse("teapot", status_code=418)

    app = Starlette(
        routes=[
            Route("/ok", ok),
            Route("/echo", echo, methods=["GET", "POST"]),
            Route("/teapot", teapot),
        ]
    )
    app.add_middleware(RequestLogMiddleware)
    return app


def _capture_log_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "admin_backend.request_log"
    ]


def _parse_single_log(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    lines = _capture_log_lines(caplog)
    assert len(lines) == 1, f"expected exactly one log line, got: {lines!r}"
    return json.loads(lines[0])


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestCoerceRequestId:
    def test_returns_input_when_valid_uuid4(self):
        valid = "550e8400-e29b-41d4-a716-446655440000"
        assert _coerce_request_id(valid) == valid

    def test_returns_new_uuid_when_none(self):
        out = _coerce_request_id(None)
        assert UUID_RE.match(out)

    def test_returns_new_uuid_when_blank(self):
        out = _coerce_request_id("   ")
        assert UUID_RE.match(out)

    def test_returns_new_uuid_when_garbage(self):
        out = _coerce_request_id("not-a-uuid")
        assert UUID_RE.match(out)

    def test_returns_new_uuid_when_uuid_v1(self):
        v1 = str(uuid.uuid1())
        out = _coerce_request_id(v1)
        assert out != v1
        assert UUID_RE.match(out)


class TestHashUserId:
    def test_empty_for_none(self):
        assert _hash_user_id(None) == ""

    def test_empty_for_empty_string(self):
        assert _hash_user_id("") == ""

    def test_sha256_hex_for_subject(self):
        subject = "user-42"
        expected = hashlib.sha256(subject.encode("utf-8")).hexdigest()
        assert _hash_user_id(subject) == expected
        assert len(expected) == 64


# ---------------------------------------------------------------------------
# Middleware behaviour through the Starlette TestClient
# ---------------------------------------------------------------------------


class TestRequestLogMiddleware:
    def test_emits_exactly_one_json_line_with_required_fields(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            response = client.get("/ok")
        assert response.status_code == 200
        record = _parse_single_log(caplog)
        for key in (
            "timestamp",
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "user_id_hash",
        ):
            assert key in record
        assert record["method"] == "GET"
        assert record["path"] == "/ok"
        assert record["status"] == 200

    def test_duration_is_integer_in_range(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            client.get("/ok")
        record = _parse_single_log(caplog)
        assert isinstance(record["duration_ms"], int)
        assert 0 <= record["duration_ms"] <= DURATION_MS_MAX

    def test_user_id_hash_empty_when_no_user(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            client.get("/ok")
        record = _parse_single_log(caplog)
        assert record["user_id_hash"] == ""

    def test_user_id_hash_is_sha256_when_user_set(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        subject = "subject-abc-123"
        with TestClient(_build_app(set_user_id=subject)) as client:
            client.get("/ok")
        record = _parse_single_log(caplog)
        assert record["user_id_hash"] == hashlib.sha256(
            subject.encode("utf-8")
        ).hexdigest()
        # Sanity: a hash, not the raw user id.
        assert subject not in record["user_id_hash"]

    def test_request_id_preserved_when_valid_uuid_header(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        rid = str(uuid.uuid4())
        with TestClient(_build_app()) as client:
            response = client.get(
                "/ok", headers={REQUEST_ID_HEADER: rid}
            )
        assert response.headers.get(REQUEST_ID_HEADER) == rid
        record = _parse_single_log(caplog)
        assert record["request_id"] == rid

    def test_request_id_replaced_when_header_invalid(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            response = client.get(
                "/ok", headers={REQUEST_ID_HEADER: "definitely-not-a-uuid"}
            )
        new_id = response.headers.get(REQUEST_ID_HEADER)
        assert new_id is not None
        assert new_id != "definitely-not-a-uuid"
        assert UUID_RE.match(new_id)
        record = _parse_single_log(caplog)
        assert record["request_id"] == new_id

    def test_request_id_generated_when_header_missing(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            response = client.get("/ok")
        new_id = response.headers.get(REQUEST_ID_HEADER)
        assert new_id is not None
        assert UUID_RE.match(new_id)
        record = _parse_single_log(caplog)
        assert record["request_id"] == new_id

    def test_status_code_propagated(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            response = client.get("/teapot")
        assert response.status_code == 418
        record = _parse_single_log(caplog)
        assert record["status"] == 418

    def test_does_not_log_query_string(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            client.get("/echo?token=secret&pii=value")
        record = _parse_single_log(caplog)
        assert record["path"] == "/echo"
        # No field carries the raw query string or its values.
        for value in record.values():
            assert "token" not in str(value)
            assert "secret" not in str(value)
            assert "pii" not in str(value)

    def test_timestamp_is_iso8601_utc(self, caplog):
        caplog.set_level(logging.INFO, logger="admin_backend.request_log")
        with TestClient(_build_app()) as client:
            client.get("/ok")
        record = _parse_single_log(caplog)
        ts: str = record["timestamp"]
        # Either ``...Z`` or ``...+00:00`` indicates UTC; the middleware
        # emits the trailing ``Z`` form.
        assert ts.endswith("Z") or ts.endswith("+00:00")
        # And it must round-trip through ``datetime.fromisoformat``.
        from datetime import datetime

        parsable = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        datetime.fromisoformat(parsable)


# ---------------------------------------------------------------------------
# Property 14: Structured Request Log (sub-task 10.4).
#
# **Validates: Requirements 17.5**
#
# For every random ``(method, path, status, user_id)`` tuple, sending one
# request through ``RequestLogMiddleware`` must emit *exactly one* JSON
# log line carrying the seven required fields with the correct types and
# ranges, and the ``user_id_hash`` field must be empty *iff* the request
# was unauthenticated. ``duration_ms`` is observed (not generated) and
# must always land in ``[0, DURATION_MS_MAX]`` per design C13.
# ---------------------------------------------------------------------------

import string
from datetime import datetime, timedelta, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from starlette.responses import Response


_PROPERTY_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
_PATH_ALPHABET = string.ascii_letters + "/-_"


class _MemoryLogHandler(logging.Handler):
    """In-memory log handler that records every emitted record verbatim.

    Per-example handlers are attached and detached around a single
    request so that one Hypothesis draw cannot observe log lines from a
    previous draw.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        self.records.append(record)


def _build_property_app(*, status: int, user_id: str | None) -> Starlette:
    """Build a Starlette app that returns ``status`` and surfaces ``user_id``.

    A single catch-all route handles every method/path combination
    drawn by Hypothesis. ``request.state.user_id`` is left unset when
    ``user_id is None`` so the middleware exercises its
    ``getattr(..., None)`` branch.
    """

    async def handler(request: Request) -> Response:
        if user_id is not None:
            request.state.user_id = user_id
        return Response(b"", status_code=status)

    app = Starlette(
        routes=[Route("/{full_path:path}", handler, methods=_PROPERTY_METHODS)]
    )
    app.add_middleware(RequestLogMiddleware)
    return app


@given(
    method=st.sampled_from(_PROPERTY_METHODS),
    path=st.text(alphabet=_PATH_ALPHABET, min_size=1, max_size=50).map(
        lambda s: "/" + s.lstrip("/")
    ),
    # Task 10.4 specifies ``integers(100, 599)`` but 1xx interim responses
    # cannot be delivered as a *final* response through Starlette's
    # ``TestClient`` (httpx waits for a 2xx-5xx). Restricting the lower
    # bound to 200 keeps the property meaningful (the middleware records
    # whatever status the response carries) while staying within the
    # reachable status-code space of the test harness.
    status=st.integers(min_value=200, max_value=599),
    user_id=st.one_of(st.none(), st.text(min_size=0, max_size=64)),
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example],
)
def test_property_14_structured_request_log(
    method: str, path: str, status: int, user_id: str | None
) -> None:
    """**Validates: Requirements 17.5**

    Property 14 - Structured Request Log: a single round-trip through
    ``RequestLogMiddleware`` produces exactly one valid JSON log line
    carrying ``timestamp``, ``request_id``, ``method``, ``path``,
    ``status``, ``duration_ms``, and ``user_id_hash`` with the types
    and ranges promised by the design, and ``user_id_hash == ""`` iff
    the request was unauthenticated.
    """
    handler = _MemoryLogHandler()
    request_logger = logging.getLogger("admin_backend.request_log")
    prior_level = request_logger.level
    prior_propagate = request_logger.propagate
    request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    # Block propagation to avoid pollution from / by parent handlers
    # (e.g. caplog) for the duration of this draw.
    request_logger.propagate = False
    try:
        app = _build_property_app(status=status, user_id=user_id)
        with TestClient(app) as client:
            response = client.request(method, path)
    finally:
        request_logger.removeHandler(handler)
        request_logger.setLevel(prior_level)
        request_logger.propagate = prior_propagate

    # Exactly one log line emitted (no extras, no drops).
    assert len(handler.records) == 1, (
        "expected exactly one log line, got "
        f"{len(handler.records)}: "
        f"{[r.getMessage() for r in handler.records]!r}"
    )
    raw = handler.records[0].getMessage()

    # The single line parses as JSON.
    payload = json.loads(raw)
    assert isinstance(payload, dict)

    # Every required field is present.
    required_fields = {
        "timestamp",
        "request_id",
        "method",
        "path",
        "status",
        "duration_ms",
        "user_id_hash",
    }
    missing = required_fields - set(payload.keys())
    assert not missing, f"missing required fields: {missing}"

    # method/path/status echo the inbound request.
    assert payload["method"] == method
    assert payload["path"] == path
    assert response.status_code == status
    assert isinstance(payload["status"], int)
    # ``bool`` is a subclass of ``int``; reject it explicitly.
    assert not isinstance(payload["status"], bool)
    assert payload["status"] == status

    # duration_ms is an integer clamped into [0, DURATION_MS_MAX].
    assert isinstance(payload["duration_ms"], int)
    assert not isinstance(payload["duration_ms"], bool)
    assert 0 <= payload["duration_ms"] <= DURATION_MS_MAX

    # user_id_hash is a string, and is empty iff the request was
    # unauthenticated (None or empty subject).
    assert isinstance(payload["user_id_hash"], str)
    unauthenticated = user_id is None or user_id == ""
    if unauthenticated:
        assert payload["user_id_hash"] == "", (
            "expected empty user_id_hash for unauthenticated request, got "
            f"{payload['user_id_hash']!r}"
        )
    else:
        expected_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        assert payload["user_id_hash"] == expected_hash
        assert len(payload["user_id_hash"]) == 64
        # Hex digits only.
        assert all(c in "0123456789abcdef" for c in payload["user_id_hash"])

    # request_id is a valid UUIDv4.
    request_id = payload["request_id"]
    assert isinstance(request_id, str)
    assert UUID_RE.match(request_id) is not None, (
        f"request_id is not a valid UUIDv4: {request_id!r}"
    )
    parsed_uuid = uuid.UUID(request_id)
    assert parsed_uuid.version == 4
    # And the response carries the same id back to the client.
    assert response.headers.get(REQUEST_ID_HEADER) == request_id

    # timestamp parses as ISO 8601 in UTC.
    ts = payload["timestamp"]
    assert isinstance(ts, str)
    assert ts.endswith("Z") or ts.endswith("+00:00"), (
        f"timestamp is not UTC ISO 8601: {ts!r}"
    )
    parsable = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    parsed_dt = datetime.fromisoformat(parsable)
    assert parsed_dt.tzinfo is not None
    assert parsed_dt.utcoffset() == timedelta(0)
    # And it must round-trip to a tz-aware UTC instant.
    assert parsed_dt == parsed_dt.astimezone(timezone.utc)
