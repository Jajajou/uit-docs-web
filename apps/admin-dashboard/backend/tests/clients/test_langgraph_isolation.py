"""Property test for upstream isolation (task 9.6).

Property 4: Upstream Isolation.

**Validates: Requirements 14.4, 14.6, 14.9**

A degraded LangGraph upstream must be **contained**: every
LangGraph-dependent route MUST return HTTP 503 carrying a
``Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}`` envelope, and the
raw upstream body (or transport-error message) MUST NOT leak into the
response.  At the same time, every non-LangGraph-dependent route
continues to serve traffic with HTTP 200 regardless of upstream
health.  This is correctness Property 4 (CP-4) in the design and the
heart of the "containment" goal stated in the design's Goals section.

The Hypothesis strategy enumerates the failure-mode × route cartesian
product the design treats as containment-relevant:

* failure modes:
  ``conn_refused`` -> :class:`httpx.ConnectError` ("connection refused"),
  ``dns``          -> :class:`httpx.ConnectError` ("dns lookup failed"),
  ``connect_timeout`` -> :class:`httpx.ConnectTimeout`,
  ``read_timeout`` -> :class:`httpx.ReadTimeout`,
  ``http_500/502/503/504`` -> :class:`httpx.Response` with that status.
* routes:
  ``lg``    -> ``/test/lg-route`` (a langgraph-dependent route that
                  delegates to ``app.state.langgraph_client``),
  ``no_lg`` -> ``/test/no-lg-route`` (a non-langgraph route that
                  returns a static body without touching the upstream).

For each example a fresh **sentinel** is generated (a 32-char hex
string from :func:`secrets.token_hex`) and woven into both the
transport-error message and the 5xx response body.  The "raw upstream
body must not leak" assertion is therefore genuine — the only way the
sentinel could appear in the response is if the SUT propagated the
upstream body or exception message verbatim, which is exactly what
Requirement 14.6 forbids.

Run from ``web/apps/admin-dashboard/backend``::

    pytest tests/clients/test_langgraph_isolation.py -v
"""

from __future__ import annotations

import asyncio
import secrets
from typing import Awaitable, Callable, Literal

import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given
from hypothesis import settings as hypo_settings
from hypothesis import strategies as st

from app.clients.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    ProbeResult,
)
from app.clients.langgraph import LangGraphClient, LangGraphUnavailable
from app.core.errors import StructuredErrorCode
from app.core.settings import Settings, reset_settings_cache
from app.main import create_app


# ---------------------------------------------------------------------------
# Fixed configuration shared by every Hypothesis example
# ---------------------------------------------------------------------------

VALID_URL = "https://upstream.test"
ALLOWED_ORIGIN = "https://admin.example.com"
ALLOWED_HOST = "admin.example.com"

#: Path mounted by the langgraph-dependent test route.
LG_PATH = "/test/lg-route"

#: Path mounted by the non-langgraph test route.
NO_LG_PATH = "/test/no-lg-route"

#: Upstream path the langgraph-dependent route asks the client to call.
#: Mirrors the contract surface listed in design section C10 / R15.3.
UPSTREAM_PATH = "/threads"


FailureMode = Literal[
    "conn_refused",
    "dns",
    "connect_timeout",
    "read_timeout",
    "http_500",
    "http_502",
    "http_503",
    "http_504",
]


FAILURE_MODE_STRATEGY = st.sampled_from(
    [
        "conn_refused",
        "dns",
        "connect_timeout",
        "read_timeout",
        "http_500",
        "http_502",
        "http_503",
        "http_504",
    ]
)


#: Two-element route partition matching the design's "fixture set
#: partitioned into ``langgraph_dependent`` and ``non_langgraph_dependent``"
#: language.  We keep the labels short here and translate them into
#: paths inside the test body.
ROUTE_STRATEGY = st.sampled_from(["lg", "no_lg"])


def _build_settings() -> Settings:
    """Build a non-misconfigured :class:`Settings` for the test app."""

    return Settings(
        LANGGRAPH_UPSTREAM_URL=VALID_URL,  # type: ignore[arg-type]
        CORS_ALLOWED_ORIGINS=ALLOWED_ORIGIN,  # type: ignore[arg-type]
        TRUSTED_HOSTS=ALLOWED_HOST,  # type: ignore[arg-type]
        ENV="production",  # type: ignore[arg-type]
    )


def _stub_probe_factory(
    rv: ProbeResult = 200,
) -> Callable[[LangGraphClient], Callable[[], Awaitable[ProbeResult]]]:
    """Probe factory that yields ``rv`` without making any HTTP call.

    The breaker's probe loop runs in the lifespan's event loop alongside
    our test; we hand it a coroutine that returns a fixed status after
    a single ``asyncio.sleep(0)`` so the loop cooperates with
    cancellation but never escapes to the network.
    """

    async def _probe() -> ProbeResult:
        await asyncio.sleep(0)
        return rv

    def factory(_client: LangGraphClient) -> Callable[[], Awaitable[ProbeResult]]:
        return _probe

    return factory


def _attach_test_routes(app: FastAPI) -> None:
    """Mount the two test routes onto ``app``.

    The langgraph-dependent route delegates to
    ``request.app.state.langgraph_client.request(...)`` (the contract
    wired in task 9.4) and maps the client's
    :class:`LangGraphUnavailable` exception to HTTP 503 +
    ``Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}`` exactly as
    Requirements 14.4, 14.6 and 14.9 demand.  The non-langgraph route
    is a constant function so the test can prove that upstream
    failures don't leak across containment boundaries.
    """

    @app.get(LG_PATH)
    async def lg_route(request: Request):  # noqa: D401 - test fixture
        try:
            response = await request.app.state.langgraph_client.request(
                "GET", UPSTREAM_PATH
            )
        except LangGraphUnavailable as exc:
            return JSONResponse(
                status_code=503,
                content=exc.structured_error.model_dump(),
            )
        # Successful upstream response — round-trip the status only.
        # The property test stubs every example with a failure mode so
        # this branch is never exercised in production runs of this
        # file, but we still keep it well-defined to avoid an implicit
        # ``None`` body if the breaker ever short-circuited via a
        # successful probe race.
        return {"upstream_status": response.status_code}

    @app.get(NO_LG_PATH)
    async def no_lg_route():  # noqa: D401 - test fixture
        return {"ok": True}


def _reset_breaker(breaker: CircuitBreaker) -> None:
    """Reset ``breaker`` to a freshly-Closed state between examples.

    Property 4 measures the **per-call** isolation contract, not the
    rolling-window trip behaviour (Property 9 covers that).  Without a
    reset, a sequence of failure examples would accumulate failures
    in the breaker's 60-second window and trip it; subsequent examples
    would short-circuit via the breaker's open state and never reach
    respx, hiding the "upstream body must not leak" assertion.
    """

    # Direct dataclass replacement is safe in tests: the breaker has
    # an asyncio.Lock that gates ``on_success``/``on_failure``, but
    # nothing reads ``_state`` while the synchronous TestClient call
    # is in flight (the probe loop is the only other writer and it
    # only runs every 30s).
    breaker._state = CircuitBreakerState()  # noqa: SLF001 — test reset


def _stub_failure(
    router: respx.Router,
    *,
    mode: FailureMode,
    sentinel: str,
) -> respx.Route:
    """Configure a respx route that realises ``mode`` for the upstream.

    Each transport-error mode raises a fresh exception whose message
    carries ``sentinel``; each 5xx mode returns a response whose body
    carries the same sentinel.  The test later asserts the sentinel
    never reaches the client-facing response.
    """

    if mode == "conn_refused":
        return router.get(UPSTREAM_PATH).mock(
            side_effect=httpx.ConnectError(
                f"Connection refused: {sentinel}"
            )
        )
    if mode == "dns":
        return router.get(UPSTREAM_PATH).mock(
            side_effect=httpx.ConnectError(
                f"DNS lookup failed: {sentinel}"
            )
        )
    if mode == "connect_timeout":
        return router.get(UPSTREAM_PATH).mock(
            side_effect=httpx.ConnectTimeout(
                f"Connect timeout: {sentinel}"
            )
        )
    if mode == "read_timeout":
        return router.get(UPSTREAM_PATH).mock(
            side_effect=httpx.ReadTimeout(
                f"Read timeout: {sentinel}"
            )
        )

    status_for_mode = {
        "http_500": 500,
        "http_502": 502,
        "http_503": 503,
        "http_504": 504,
    }
    return router.get(UPSTREAM_PATH).mock(
        return_value=httpx.Response(
            status_for_mode[mode],
            text=f"upstream body: {sentinel}",
        )
    )


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app_and_client():
    """Build the test FastAPI app + :class:`TestClient` once per module.

    The app is constructed via :func:`app.main.create_app` so the
    production middleware stack (CORS, trusted-host, request-log,
    metrics) wraps the langgraph routes the same way it would at
    runtime.  After the lifespan starts we swap
    ``app.state.langgraph_client`` for a fast-retry client
    (``max_attempts=1``, zero waits) so the property test completes in
    seconds instead of minutes — Property 4 cares about the 503
    mapping, not the retry-count contract (Property 9 covers that).
    """

    reset_settings_cache()
    app = create_app(
        settings=_build_settings(),
        probe_fn_factory=_stub_probe_factory(200),
    )
    _attach_test_routes(app)

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}") as client:
        breaker: CircuitBreaker = app.state.circuit_breaker
        fast_client = LangGraphClient(
            VALID_URL,
            breaker,
            max_attempts=1,
            retry_wait_multiplier=0.0,
            retry_wait_min=0.0,
            retry_wait_max=0.0,
        )
        # The lifespan-built client is closed for us by the lifespan
        # shutdown hook; the fast client we install here is closed
        # explicitly below so we don't leak an httpx connection pool
        # across test sessions.
        app.state.langgraph_client = fast_client
        try:
            yield app, client
        finally:
            try:
                asyncio.run(fast_client.aclose())
            except Exception:  # noqa: BLE001 — test cleanup, swallow
                pass

    reset_settings_cache()


# ---------------------------------------------------------------------------
# Property
# ---------------------------------------------------------------------------


@hypo_settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    failure_mode=FAILURE_MODE_STRATEGY,
    route=ROUTE_STRATEGY,
)
def test_upstream_isolation(
    app_and_client: tuple[FastAPI, TestClient],
    failure_mode: FailureMode,
    route: str,
) -> None:
    """**Validates: Requirements 14.4, 14.6, 14.9**

    For every (failure_mode, route) pair drawn by Hypothesis:

    * non-LangGraph routes return HTTP 200 with the static
      ``{"ok": True}`` body — they never call the upstream and so
      remain available even when LangGraph is degraded (R14.4).
    * LangGraph routes return HTTP 503 with a
      ``Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}`` envelope
      (R14.9) and the raw upstream body or transport-error message
      MUST NOT be echoed in the response (R14.6).
    """

    app, client = app_and_client
    breaker: CircuitBreaker = app.state.circuit_breaker

    # Reset the breaker so each example exercises the same starting
    # state (Closed) — see ``_reset_breaker`` for rationale.
    _reset_breaker(breaker)

    sentinel = secrets.token_hex(16)

    with respx.mock(base_url=VALID_URL, assert_all_called=False) as router:
        _stub_failure(router, mode=failure_mode, sentinel=sentinel)

        target = LG_PATH if route == "lg" else NO_LG_PATH
        response = client.get(target)

    # ------------------------------------------------------------------
    # Non-LangGraph route: must serve traffic regardless of upstream.
    # ------------------------------------------------------------------
    if route == "no_lg":
        assert response.status_code == 200, (
            f"non-LG route must return 200 regardless of upstream "
            f"failure_mode={failure_mode!r}; got "
            f"{response.status_code} body={response.text!r}"
        )
        assert response.json() == {"ok": True}, (
            f"non-LG route body must be the static "
            f"{{'ok': True}}; got {response.json()!r}"
        )
        # Defensive: a non-LG route must NEVER touch the upstream, so
        # the sentinel cannot have leaked even theoretically.
        assert sentinel not in response.text, (
            f"sentinel leaked into non-LG response under "
            f"failure_mode={failure_mode!r}: {response.text!r}"
        )
        return

    # ------------------------------------------------------------------
    # LangGraph-dependent route: must surface the structured 503.
    # ------------------------------------------------------------------
    assert response.status_code == 503, (
        f"LG route under failure_mode={failure_mode!r} expected HTTP "
        f"503; got {response.status_code} body={response.text!r}"
    )

    payload = response.json()

    # Envelope shape from design D1.
    assert set(payload.keys()) == {
        "code",
        "message",
        "request_id",
        "timestamp",
    }, (
        f"unexpected Structured_Error envelope keys under "
        f"failure_mode={failure_mode!r}: {sorted(payload)!r}"
    )
    assert payload["code"] == "LANGGRAPH_UNAVAILABLE", (
        f"LG route under failure_mode={failure_mode!r} expected "
        f"code='LANGGRAPH_UNAVAILABLE'; got {payload['code']!r}"
    )

    # ``code`` must round-trip through the closed set declared in
    # :data:`StructuredErrorCode` (design D1).
    allowed_codes = set(StructuredErrorCode.__args__)  # type: ignore[attr-defined]
    assert payload["code"] in allowed_codes
    assert isinstance(payload["message"], str) and payload["message"]
    assert isinstance(payload["request_id"], str) and payload["request_id"]
    assert isinstance(payload["timestamp"], str) and payload["timestamp"]

    # Containment: the raw upstream body / exception message must NOT
    # leak into the structured response (R14.6).
    assert sentinel not in response.text, (
        f"upstream sentinel leaked into LG response under "
        f"failure_mode={failure_mode!r}: {response.text!r}"
    )
