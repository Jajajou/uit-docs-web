"""Property-based test for the ``/healthz`` endpoint (task 9.8).

Property 7: Health-Endpoint Consistency.

**Validates: Requirements 14.7**

For any breaker state ``S`` drawn from
``{"Closed", "Open", "HalfOpen_success_0", "HalfOpen_success_1"}``,
the ``GET /healthz`` endpoint exposed by ``Admin_Backend`` SHALL return:

* HTTP **200** with body ``{"status":"ok"}`` if and only if ``S`` is
  ``Closed`` or any ``HalfOpen`` variant; and
* HTTP **503** with a ``Structured_Error`` whose ``code`` equals
  ``"LANGGRAPH_UNAVAILABLE"`` if and only if ``S`` is ``Open``.

This is the property-test counterpart to the example-based suite in
``tests/api/test_healthz.py``.  Where that suite covers each of the
three documented serving states once, this suite drives the breaker
into a randomly chosen state on every Hypothesis example and asserts
the response code mapping holds.

Test strategy
-------------
* States are drawn from ``sampled_from(["Closed", "Open",
  "HalfOpen_success_0", "HalfOpen_success_1"])`` so the property
  exercises the two ``HalfOpen`` shapes called out by the task
  description (``success_count ∈ {0, 1}``) — both must serve traffic
  with HTTP 200.
* The breaker is driven into the chosen state by calling its public
  primitives (:meth:`CircuitBreaker.on_failure`,
  :meth:`CircuitBreaker.on_success`) and the ``_enter_half_open``
  helper that the probe loop itself uses (design C10).  No fields are
  mutated directly so the property cannot accidentally pass by
  bypassing the state machine.
* Every example uses a fresh :class:`fastapi.testclient.TestClient`
  bound to a fresh ``create_app`` instance; this guarantees each
  example starts from a clean breaker, lifespan, and listener stack
  (so the metrics gauge in design C13 cannot leak across examples).
* The probe factory injected into ``create_app`` returns ``200``
  without making real HTTP calls so the property runs offline in CI.
* ``max_examples=50`` per the task description.

Run from ``web/apps/admin-dashboard/backend``::

    pytest tests/clients/test_healthz_state.py
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Literal

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings as hypo_settings
from hypothesis import strategies as st

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

# ---------------------------------------------------------------------------
# Fixed configuration shared by every Hypothesis example
# ---------------------------------------------------------------------------

VALID_URL = "https://langgraph.example.com"
ALLOWED_ORIGIN = "https://admin.example.com"
ALLOWED_HOST = "admin.example.com"

# The four state labels enumerated by the task description.  They map
# 1-to-1 to the breaker shapes that ``/healthz`` must distinguish:
#
#   * ``Closed``                — the post-startup default (design C10).
#   * ``Open``                  — tripped by ≥5 failures (R14.4).
#   * ``HalfOpen_success_0``    — Open -> HalfOpen via the probe loop
#                                 helper, before any 2xx probe lands.
#   * ``HalfOpen_success_1``    — same, plus one banked 2xx probe so
#                                 the breaker is one success short of
#                                 closing (R14.5).
StateLabel = Literal[
    "Closed", "Open", "HalfOpen_success_0", "HalfOpen_success_1"
]

STATE_STRATEGY = st.sampled_from(
    ["Closed", "Open", "HalfOpen_success_0", "HalfOpen_success_1"]
)


def _build_settings() -> Settings:
    """Return a non-misconfigured :class:`Settings` for the test app."""

    return Settings(
        LANGGRAPH_UPSTREAM_URL=VALID_URL,  # type: ignore[arg-type]
        CORS_ALLOWED_ORIGINS=ALLOWED_ORIGIN,  # type: ignore[arg-type]
        TRUSTED_HOSTS=ALLOWED_HOST,  # type: ignore[arg-type]
        ENV="production",  # type: ignore[arg-type]
    )


def _stub_probe_factory(
    return_value: ProbeResult = 200,
) -> Callable[[LangGraphClient], Callable[[], Awaitable[ProbeResult]]]:
    """Build a probe factory that yields ``return_value`` without I/O.

    The breaker's probe loop must not make real network calls during
    the property run, so we hand it a coroutine that returns a fixed
    HTTP status after a single ``asyncio.sleep(0)`` (to cooperate with
    cancellation points).
    """

    async def _probe() -> ProbeResult:
        await asyncio.sleep(0)
        return return_value

    def factory(_client: LangGraphClient) -> Callable[[], Awaitable[ProbeResult]]:
        return _probe

    return factory


def _drive_breaker_into(breaker: CircuitBreaker, label: StateLabel) -> None:
    """Move ``breaker`` into the state described by ``label``.

    The driver uses only the breaker's public primitives plus the
    ``_enter_half_open`` helper that the probe loop itself uses
    (design C10), so the breaker's invariants — failure-window
    bookkeeping, ``opened_at`` timestamp, ``success_count`` reset on
    transition — are exercised exactly the way production traffic
    would exercise them.  Mutating fields directly would let the
    property pass by bypassing the state machine, defeating the point
    of the test.
    """

    async def _drive() -> None:
        if label == "Closed":
            # Freshly-built breakers start Closed; no work needed.
            return

        # All non-Closed labels start by tripping the breaker, so do
        # that once up front.
        for _ in range(breaker.failure_threshold):
            await breaker.on_failure()
        assert breaker.state == BreakerState.OPEN

        if label == "Open":
            return

        # Open -> HalfOpen using the same private helper the probe
        # loop calls (design C10).  This leaves ``success_count`` at
        # 0 — the ``HalfOpen_success_0`` shape.
        await breaker._enter_half_open()  # noqa: SLF001 — internal helper
        assert breaker.state == BreakerState.HALF_OPEN
        assert breaker.snapshot.success_count == 0

        if label == "HalfOpen_success_0":
            return

        # Bank exactly one 2xx probe.  With the default
        # ``half_open_required_successes=2`` this leaves the breaker
        # in HalfOpen with ``success_count == 1`` — the
        # ``HalfOpen_success_1`` shape.
        assert breaker.half_open_required_successes >= 2, (
            "test assumes the default half-open success threshold"
        )
        await breaker.on_success()
        assert breaker.state == BreakerState.HALF_OPEN
        assert breaker.snapshot.success_count == 1

    asyncio.run(_drive())


def _expected_status_code(label: StateLabel) -> int:
    """Truth oracle for Property 7.

    The oracle is intentionally written as an independent mapping
    rather than a delegate to the breaker so a property failure means
    the SUT and the design's stated contract genuinely disagree.
    """

    if label == "Open":
        return 503
    return 200


# ---------------------------------------------------------------------------
# Property
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Ensure each Hypothesis example sees a freshly-loaded :class:`Settings`."""

    reset_settings_cache()
    yield
    reset_settings_cache()


@hypo_settings(
    max_examples=50,
    # Each example needs its own ``create_app`` + ``TestClient`` to
    # isolate breaker state, so we deliberately rebuild within the
    # function body rather than via a function-scoped fixture.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(state_label=STATE_STRATEGY)
def test_healthz_response_matches_breaker_state(state_label: StateLabel) -> None:
    """**Validates: Requirements 14.7**

    For every breaker state in the closed set, ``GET /healthz`` returns
    the response code mandated by Property 7 — 200 for ``Closed`` and
    every ``HalfOpen`` variant, 503 for ``Open``.  In the 503 path the
    response body must be a :class:`Structured_Error` envelope whose
    ``code`` is the closed-set value ``"LANGGRAPH_UNAVAILABLE"``.
    """

    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}") as client:
        breaker: CircuitBreaker = client.app.state.circuit_breaker

        _drive_breaker_into(breaker, state_label)

        # Sanity: the breaker really sits in the requested state
        # before we hit the endpoint.  This guards against a future
        # refactor of ``_drive_breaker_into`` silently regressing.
        if state_label == "Closed":
            assert breaker.state == BreakerState.CLOSED
        elif state_label == "Open":
            assert breaker.state == BreakerState.OPEN
        else:
            assert breaker.state == BreakerState.HALF_OPEN
            expected_count = 0 if state_label == "HalfOpen_success_0" else 1
            assert breaker.snapshot.success_count == expected_count

        response = client.get(HEALTHZ_PATH)

    expected = _expected_status_code(state_label)
    assert response.status_code == expected, (
        f"state={state_label!r} expected HTTP {expected}, "
        f"got {response.status_code}"
    )

    payload = response.json()
    if expected == 200:
        # Closed and HalfOpen serve traffic with the canonical
        # ``{"status":"ok"}`` body documented in design C10.
        assert payload == {"status": "ok"}, (
            f"state={state_label!r} expected 200 body {{'status': 'ok'}}, "
            f"got {payload!r}"
        )
    else:
        # Open responses must be a Structured_Error envelope (design
        # D1) whose ``code`` is locked to ``LANGGRAPH_UNAVAILABLE``.
        assert set(payload.keys()) == {
            "code",
            "message",
            "request_id",
            "timestamp",
        }, f"unexpected envelope keys: {sorted(payload)!r}"
        assert payload["code"] == "LANGGRAPH_UNAVAILABLE"

        # ``code`` must round-trip through the closed set declared in
        # :data:`StructuredErrorCode`.
        allowed_codes = set(StructuredErrorCode.__args__)  # type: ignore[attr-defined]
        assert payload["code"] in allowed_codes
        assert isinstance(payload["message"], str) and payload["message"]
        assert isinstance(payload["request_id"], str) and payload["request_id"]
        assert isinstance(payload["timestamp"], str) and payload["timestamp"]
