"""Unit tests for the ``/healthz`` endpoint (task 9.5, R14.7).

The contract under test is the table from design section C10 and
correctness Property 7:

==============  ====  =================================================
Breaker state   HTTP  Body
==============  ====  =================================================
``Closed``      200   ``{"status":"ok"}``
``HalfOpen``    200   ``{"status":"ok"}``
``Open``        503   ``Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}``
==============  ====  =================================================

These three breaker states are exercised end-to-end via
:func:`app.main.create_app` so the routing wired by task 9.5 is
verified in lockstep with the lifespan + middleware stack from tasks
9.4 and 10.1.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import pytest
from fastapi.testclient import TestClient

from app.api.health import HEALTHZ_PATH
from app.clients.circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    ProbeResult,
)
from app.clients.langgraph import LangGraphClient
from app.core.errors import StructuredErrorCode
from app.core.settings import Settings, reset_settings_cache
from app.main import create_app

VALID_URL = "https://langgraph.example.com"
ALLOWED_ORIGIN = "https://admin.example.com"
ALLOWED_HOST = "admin.example.com"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    reset_settings_cache()
    yield
    reset_settings_cache()


def _build_settings() -> Settings:
    """Build a non-misconfigured :class:`Settings` for the test app."""

    return Settings(
        LANGGRAPH_UPSTREAM_URL=VALID_URL,  # type: ignore[arg-type]
        CORS_ALLOWED_ORIGINS=ALLOWED_ORIGIN,  # type: ignore[arg-type]
        TRUSTED_HOSTS=ALLOWED_HOST,  # type: ignore[arg-type]
        ENV="production",  # type: ignore[arg-type]
    )


def _stub_probe_factory(
    return_value: ProbeResult = 200,
) -> Callable[[LangGraphClient], Callable[[], Awaitable[ProbeResult]]]:
    """Build a probe factory that returns ``return_value`` without HTTP.

    The breaker's probe loop must not make real network calls during
    these tests, so we hand it a coroutine that yields a fixed value
    after a single ``asyncio.sleep(0)`` (to cooperate with the loop's
    cancellation points).
    """

    async def _probe() -> ProbeResult:
        await asyncio.sleep(0)
        return return_value

    def factory(_client: LangGraphClient) -> Callable[[], Awaitable[ProbeResult]]:
        return _probe

    return factory


def _build_client() -> TestClient:
    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )
    return TestClient(app, base_url=f"http://{ALLOWED_HOST}")


# ---------------------------------------------------------------------------
# Closed -> 200
# ---------------------------------------------------------------------------


def test_healthz_returns_200_when_breaker_is_closed() -> None:
    """**Validates: Requirements 14.7**

    A freshly built app starts with the breaker in ``Closed`` and
    must respond ``200 {"status":"ok"}``.
    """

    with _build_client() as client:
        breaker: CircuitBreaker = client.app.state.circuit_breaker
        assert breaker.state == BreakerState.CLOSED

        response = client.get(HEALTHZ_PATH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# HalfOpen -> 200
# ---------------------------------------------------------------------------


def test_healthz_returns_200_when_breaker_is_half_open() -> None:
    """**Validates: Requirements 14.7**

    Design C10 documents ``HalfOpen`` as a serving state — the
    endpoint must return ``200 {"status":"ok"}`` so traffic can resume
    while the probe loop confirms recovery.
    """

    with _build_client() as client:
        breaker: CircuitBreaker = client.app.state.circuit_breaker

        async def _drive() -> None:
            for _ in range(breaker.failure_threshold):
                await breaker.on_failure()
            assert breaker.state == BreakerState.OPEN
            # ``_enter_half_open`` is the same private helper the
            # probe loop uses to transition Open -> HalfOpen.
            await breaker._enter_half_open()  # noqa: SLF001 — internal helper

        asyncio.run(_drive())
        assert breaker.state == BreakerState.HALF_OPEN

        response = client.get(HEALTHZ_PATH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Open -> 503 + Structured_Error
# ---------------------------------------------------------------------------


def test_healthz_returns_503_with_structured_error_when_breaker_is_open() -> None:
    """**Validates: Requirements 14.7**

    Tripping the breaker must turn ``/healthz`` into a 503 carrying
    the closed-set ``LANGGRAPH_UNAVAILABLE`` envelope (design D1).
    """

    with _build_client() as client:
        breaker: CircuitBreaker = client.app.state.circuit_breaker

        async def _trip() -> None:
            for _ in range(breaker.failure_threshold):
                await breaker.on_failure()

        asyncio.run(_trip())
        assert breaker.state == BreakerState.OPEN

        response = client.get(HEALTHZ_PATH)

    assert response.status_code == 503
    payload = response.json()
    # The response is a model_dump() of a Structured_Error envelope —
    # all four fields from design D1 must be present.
    assert set(payload.keys()) == {"code", "message", "request_id", "timestamp"}
    assert payload["code"] == "LANGGRAPH_UNAVAILABLE"
    # ``code`` must be a member of the closed set declared in
    # :data:`StructuredErrorCode` so the envelope round-trips through
    # the model without a validation error.
    allowed_codes = set(StructuredErrorCode.__args__)  # type: ignore[attr-defined]
    assert payload["code"] in allowed_codes
    assert isinstance(payload["message"], str) and payload["message"]
    assert isinstance(payload["request_id"], str) and payload["request_id"]
    assert isinstance(payload["timestamp"], str) and payload["timestamp"]
