"""Tests for the Prometheus metrics endpoint (task 10.5, R17.6).

These tests cover the deterministic surface of design C13:

* ``/metrics`` exposes the four metric names enumerated by C13:
  ``http_requests_total``, ``http_request_duration_seconds``,
  ``langgraph_upstream_failures_total`` (with the ``kind`` label set
  enumerated for the three allowed kinds), and ``langgraph_circuit_state``.
* ``langgraph_circuit_state`` is updated **synchronously** when the
  breaker transitions, and the gauge value follows design C13's
  encoding (``Closed=0``, ``HalfOpen=1``, ``Open=2``).

The test app is built via :func:`app.main.create_app` so the wiring
done by task 10.5 is exercised end-to-end (instrumentator + listener +
gauge).  A stub probe factory keeps the breaker's probe loop from
issuing any real HTTP traffic.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import pytest
from fastapi.testclient import TestClient

from app.api.metrics import (
    ALLOWED_FAILURE_KINDS,
    CIRCUIT_STATE_VALUES,
    METRICS_ENDPOINT,
)
from app.clients.circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    ProbeResult,
)
from app.clients.langgraph import LangGraphClient
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
    return Settings(
        LANGGRAPH_UPSTREAM_URL=VALID_URL,  # type: ignore[arg-type]
        CORS_ALLOWED_ORIGINS=ALLOWED_ORIGIN,  # type: ignore[arg-type]
        TRUSTED_HOSTS=ALLOWED_HOST,  # type: ignore[arg-type]
        ENV="production",  # type: ignore[arg-type]
    )


def _stub_probe_factory(
    return_value: ProbeResult = 200,
) -> Callable[[LangGraphClient], Callable[[], Awaitable[ProbeResult]]]:
    """Probe factory that never makes real HTTP calls."""

    async def _probe() -> ProbeResult:
        await asyncio.sleep(0)
        return return_value

    def factory(_client: LangGraphClient) -> Callable[[], Awaitable[ProbeResult]]:
        return _probe

    return factory


def _scrape(client: TestClient) -> str:
    response = client.get(
        METRICS_ENDPOINT, headers={"host": ALLOWED_HOST}
    )
    assert response.status_code == 200, response.text
    return response.text


# ---------------------------------------------------------------------------
# Endpoint exposes the four C13 metric names
# ---------------------------------------------------------------------------


def test_metrics_endpoint_exposes_all_four_metric_names() -> None:
    """**Validates: Requirements 17.6**

    Hitting ``/metrics`` after a single request through the app must
    surface every metric name listed in design C13.
    """

    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}") as client:
        # Drive at least one non-/metrics request so the
        # instrumentator's HTTP counters/histograms have a sample.
        # ``/metrics`` itself is also instrumented but having a second
        # path keeps the assertion robust if the instrumentator ever
        # excludes its own endpoint.
        client.get("/metrics")  # warm-up; harmless if it 404s on a sub-path
        body = _scrape(client)

    expected_names = (
        "http_requests_total",
        "http_request_duration_seconds",
        "langgraph_upstream_failures_total",
        "langgraph_circuit_state",
    )
    for name in expected_names:
        assert name in body, (
            f"expected metric {name!r} to appear in /metrics output, "
            f"got:\n{body[:2000]}"
        )


def test_upstream_failures_counter_pre_registers_all_kinds() -> None:
    """``langgraph_upstream_failures_total`` is exposed with a 0-valued
    series for each kind enumerated by design C13 even before the first
    failure happens, so dashboards bind to a stable label set."""

    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}") as client:
        body = _scrape(client)

    for kind in sorted(ALLOWED_FAILURE_KINDS):
        line = f'langgraph_upstream_failures_total{{kind="{kind}"}}'
        assert line in body, (
            f"expected pre-registered series for kind={kind!r} in "
            f"/metrics output, got:\n{body[:2000]}"
        )


# ---------------------------------------------------------------------------
# Synchronous gauge update on every breaker transition
# ---------------------------------------------------------------------------


def test_circuit_state_gauge_starts_at_closed() -> None:
    """A freshly created app must report ``langgraph_circuit_state 0.0``
    (Closed) — the gauge is initialised from the breaker's startup
    state, not left at the prometheus_client default."""

    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}") as client:
        body = _scrape(client)

    closed_value = CIRCUIT_STATE_VALUES[BreakerState.CLOSED]
    assert (
        f"langgraph_circuit_state {closed_value}" in body
    ), f"expected gauge=Closed (0.0), got:\n{body[:2000]}"


def test_circuit_state_gauge_reaches_open_after_failures() -> None:
    """**Validates: Requirements 17.6**

    Driving the breaker into ``Open`` (≥5 failures inside the rolling
    window) must immediately update the gauge to ``2.0`` because
    :meth:`CircuitBreaker._notify_state_change_locked` runs the
    listener inside the breaker lock.
    """

    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}") as client:
        breaker: CircuitBreaker = app.state.circuit_breaker

        async def _trip() -> None:
            # The default failure threshold is 5; record more than
            # enough failures to drive the breaker into Open even
            # under future tweaks to the threshold.
            for _ in range(breaker.failure_threshold):
                await breaker.on_failure()

        asyncio.run(_trip())
        assert breaker.state == BreakerState.OPEN

        body = _scrape(client)

    open_value = CIRCUIT_STATE_VALUES[BreakerState.OPEN]
    assert f"langgraph_circuit_state {open_value}" in body, (
        f"expected gauge=Open ({open_value}), got:\n{body[:2000]}"
    )


def test_circuit_state_gauge_returns_to_closed_after_recovery() -> None:
    """Recovery from ``Open`` -> ``HalfOpen`` -> ``Closed`` must walk
    the gauge back through the C13 encoding."""

    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}") as client:
        breaker: CircuitBreaker = app.state.circuit_breaker

        async def _drive() -> None:
            # Trip the breaker open.
            for _ in range(breaker.failure_threshold):
                await breaker.on_failure()
            assert breaker.state == BreakerState.OPEN
            # Move to HalfOpen (the probe-loop helper); the listener
            # must have run by the time the coroutine returns.
            await breaker._enter_half_open()  # noqa: SLF001 — internal helper
            assert breaker.state == BreakerState.HALF_OPEN
            # Drive enough successes to close.
            for _ in range(breaker.half_open_required_successes):
                await breaker.on_success()
            assert breaker.state == BreakerState.CLOSED

        asyncio.run(_drive())

        body = _scrape(client)

    closed_value = CIRCUIT_STATE_VALUES[BreakerState.CLOSED]
    assert f"langgraph_circuit_state {closed_value}" in body, (
        f"expected gauge to return to Closed ({closed_value}), got:\n"
        f"{body[:2000]}"
    )
