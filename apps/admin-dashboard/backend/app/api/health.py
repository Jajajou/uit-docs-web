"""Health-check endpoint (task 9.5, R14.7, design C10).

This module exposes ``GET /healthz`` — the contract documented in
design section C10 ("Health endpoint") and codified by Requirement
14.7 + correctness Property 7:

==============  ====  =================================================
Breaker state   HTTP  Body
==============  ====  =================================================
``Closed``      200   ``{"status":"ok"}``
``HalfOpen``    200   ``{"status":"ok"}``  (treated as Closed for
                       serving purposes; CP-8 only requires Closed↔200,
                       Open↔503)
``Open``        503   ``Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}``
==============  ====  =================================================

The endpoint is the single readiness signal consumed by:

* the docker-compose healthcheck for ``admin_backend`` (design C11 —
  ``curl -fsS http://localhost:8001/healthz``),
* the production deploy workflow's post-rollout probe (design C9 —
  "poll ``/healthz`` on backend & lightrag (≤60s)"),
* and ``scripts/smoke_test.sh`` (design C12 — one of the three probe
  URLs).

Implementation notes:

* The handler reads the breaker via ``request.app.state.circuit_breaker``
  rather than capturing it from a closure so the same router survives
  ``create_app`` rebuilds (each ``create_app`` call mounts a fresh
  breaker on ``app.state``; importing ``router`` only once at module
  load must remain correct).
* The 503 path returns a freshly-minted :class:`Structured_Error`
  whose ``code`` is locked to ``"LANGGRAPH_UNAVAILABLE"``; the
  envelope's ``request_id`` and ``timestamp`` are auto-populated by
  the model so every response carries an audit trail (design D1).
* The router is registered in :func:`app.main.create_app` via
  ``app.include_router(router)``.  No prefix is used because design
  C10 anchors the path at the root.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.clients.circuit_breaker import BreakerState, CircuitBreaker
from app.core.errors import StructuredError

#: Path mounted by :data:`router`.  Kept as a module constant so
#: callers (notably :mod:`scripts/smoke_test.sh` documentation and the
#: docker-compose healthcheck strings) reference the same literal.
HEALTHZ_PATH: str = "/healthz"


router = APIRouter()


@router.get(
    HEALTHZ_PATH,
    include_in_schema=True,
    summary="LangGraph-aware liveness/readiness probe",
    response_description=(
        '200 with `{"status":"ok"}` when the LangGraph circuit '
        'breaker is `Closed` or `HalfOpen`; 503 with a '
        '`Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}` body when '
        'the breaker is `Open` (R14.7).'
    ),
)
async def healthz(request: Request) -> JSONResponse:
    """Return ``200`` unless the LangGraph breaker is ``Open``.

    The breaker is mounted on ``app.state.circuit_breaker`` by the
    FastAPI ``lifespan`` hook (task 9.4).  We read it through the
    request so the handler stays decoupled from any specific app
    instance — important because :func:`app.main.create_app` builds
    a fresh breaker per app (see task 10.5's metrics wiring, which
    binds a state listener to that specific instance).
    """

    breaker: CircuitBreaker | None = getattr(
        request.app.state, "circuit_breaker", None
    )

    # Defensive guard: if the lifespan never ran (e.g. an unusual test
    # harness builds an app without entering its context), treat the
    # missing breaker as a degraded condition.  Production paths always
    # have a breaker because ``create_app`` constructs one before the
    # lifespan starts.
    if breaker is None:
        envelope = StructuredError(
            code="LANGGRAPH_UNAVAILABLE",
            message=(
                "LangGraph circuit breaker is not initialised; "
                "Admin_Backend cannot service LangGraph-backed routes."
            ),
        )
        return JSONResponse(
            status_code=503,
            content=envelope.model_dump(),
        )

    if breaker.state == BreakerState.OPEN:
        envelope = StructuredError(
            code="LANGGRAPH_UNAVAILABLE",
            message="LangGraph circuit breaker is open.",
        )
        return JSONResponse(
            status_code=503,
            content=envelope.model_dump(),
        )

    # Closed and HalfOpen both serve traffic — design C10 explicitly
    # documents HalfOpen as 200.
    return JSONResponse(
        status_code=200,
        content={"status": "ok"},
    )


__all__ = ["HEALTHZ_PATH", "healthz", "router"]
