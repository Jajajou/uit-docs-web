"""FastAPI application shell for the new ``Admin_Backend`` package.

This module is the entry point introduced by the
``cicd-deploy-admin-dashboard`` spec.  Task 10.1 wires the
production-hardening middlewares mandated by Requirement 20:

* :class:`TrustedHostMiddleware` runs **before** :class:`CORSMiddleware`
  so a malicious ``Host`` header is rejected even when the ``Origin``
  is allow-listed (design C15, R20.6).
* When ``TRUSTED_HOSTS`` is unset/empty/unparseable, a deny-all
  middleware returns HTTP 400 + a structured log with
  ``code=TRUSTED_HOSTS_MISCONFIGURED`` (R20.7).
* When ``CORS_ALLOWED_ORIGINS`` is unset/empty/unparseable, a deny-all
  middleware returns HTTP 403 + a structured log with
  ``code=CORS_MISCONFIGURED`` (R20.5).

Task 9.4 layers the LangGraph upstream contract on top of the shell:

* The FastAPI ``lifespan`` hook instantiates a
  :class:`~app.clients.circuit_breaker.CircuitBreaker` and a
  :class:`~app.clients.langgraph.LangGraphClient`, mounts them on
  ``app.state`` so request handlers can call
  ``request.app.state.langgraph_client.request(...)``, and spawns the
  breaker's ``probe_loop`` as an :class:`asyncio.Task` stored on
  ``app.state.langgraph_probe_task`` (R14.4, R14.5).
* On shutdown the probe task is cancelled and awaited (catching
  :class:`asyncio.CancelledError`) and the client is closed via
  :meth:`LangGraphClient.aclose`.
* If :func:`get_settings` raises :class:`LangGraphUpstreamConfigError`
  (R14.8), the lifespan emits the structured error envelope **once**
  and re-raises so ``uvicorn`` exits non-zero before binding the HTTP
  port.

Subsequent tasks (9.5, 10.3, 10.5, …) layer the ``/healthz`` endpoint,
the structured request log middleware, and the Prometheus metrics
endpoint on top of this shell.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.clients.circuit_breaker import CircuitBreaker, ProbeResult
from app.clients.langgraph import LangGraphClient
from app.core.errors import StructuredError
from app.core.settings import (
    LangGraphUpstreamConfigError,
    Settings,
    get_settings,
)
from app.api import health as health_api
from app.api.metrics import setup_metrics

logger = logging.getLogger(__name__)


# Placeholder URL used only when the module-level :data:`app` is
# constructed without a valid ``LANGGRAPH_UPSTREAM_URL``.  The lifespan
# hook calls :func:`get_settings` again on real startup and surfaces
# the original :class:`LangGraphUpstreamConfigError`, so this constant
# never reaches a request handler in production.
_PLACEHOLDER_UPSTREAM_URL = "https://placeholder.invalid"


#: Probe-callable signature accepted by :func:`create_app` for tests
#: that want to inject a deterministic probe (e.g. a coroutine that
#: returns ``200`` without touching the network).  The default factory
#: built by :func:`_build_default_probe_fn` issues a short ``GET
#: <upstream>/health`` via ``httpx`` with a fixed 5-second timeout.
ProbeFnFactory = Callable[[LangGraphClient], Callable[[], Awaitable[ProbeResult]]]


# ---------------------------------------------------------------------------
# Deny-all ASGI middlewares (design C15, R20.5 / R20.7)
# ---------------------------------------------------------------------------


class _DenyAllMiddleware:
    """Reject every HTTP request with a fixed status + structured body.

    Used when ``CORS_ALLOWED_ORIGINS`` or ``TRUSTED_HOSTS`` cannot be
    parsed.  The middleware is installed instead of the regular
    ``CORSMiddleware`` / ``TrustedHostMiddleware`` so the misconfigured
    backend fails closed.

    Only HTTP traffic is guarded — websocket/lifespan messages pass
    through untouched so app startup/shutdown still complete (and the
    test client's lifespan handshake works).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        status_code: int,
        error_code: str,
        message: str,
    ) -> None:
        self.app = app
        self.status_code = status_code
        self.error_code = error_code
        self.message = message

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        envelope = StructuredError(
            code=self.error_code,  # type: ignore[arg-type]
            message=self.message,
        )
        body = envelope.model_dump_json().encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


# ---------------------------------------------------------------------------
# Structured-error logging helper
# ---------------------------------------------------------------------------


def _log_structured_error(envelope: StructuredError) -> None:
    """Emit a single JSON log line carrying ``envelope``.

    The log format mirrors design D1 so the misconfiguration shows up
    identically in CI logs, deploy logs, and runtime logs.  We use the
    standard logger with ``extra`` so downstream JSON formatters can
    attach the fields verbatim, and we also stringify the envelope into
    the message so plain-text loggers stay informative.
    """

    payload: dict[str, Any] = envelope.model_dump()
    logger.error(
        "structured_error %s",
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        extra={"structured_error": payload},
    )


# ---------------------------------------------------------------------------
# Probe function factory (task 9.4)
# ---------------------------------------------------------------------------


#: Per-probe HTTP timeout (R14.5 documents 30s upstream cadence with a
#: 5s budget for the actual probe call so it never piles up on a slow
#: upstream).  The probe uses its own short-lived ``httpx.AsyncClient``
#: rather than reusing :class:`LangGraphClient` because the latter would
#: feed every probe through the breaker's retry/failure book-keeping
#: again, which is exactly what the probe loop is trying to drive.
_PROBE_TIMEOUT_SECONDS: float = 5.0


def _build_default_probe_fn(
    client: LangGraphClient,
) -> Callable[[], Awaitable[ProbeResult]]:
    """Build the default probe coroutine for ``client``.

    The returned coroutine issues a single ``GET <base>/health`` with a
    fixed 5-second timeout (per R14.5) and returns the resulting HTTP
    status code as an ``int``.  Any transport error or timeout is
    converted to ``0`` so the breaker treats it as a non-2xx outcome
    via :func:`app.clients.circuit_breaker._is_success`.
    """

    base_url = client.base_url.rstrip("/")
    health_url = f"{base_url}/health"

    async def _probe() -> ProbeResult:
        try:
            async with httpx.AsyncClient(
                timeout=_PROBE_TIMEOUT_SECONDS,
            ) as probe_client:
                response = await probe_client.get(health_url)
                return response.status_code
        except (
            httpx.TimeoutException,
            httpx.TransportError,
            httpx.HTTPError,
        ):
            return 0

    return _probe


# ---------------------------------------------------------------------------
# Middleware installation (design C15)
# ---------------------------------------------------------------------------


def _install_cors_middleware(app: FastAPI, settings: Settings) -> None:
    """Install ``CORSMiddleware`` or its deny-all stand-in (R20.4 / R20.5)."""

    if settings.cors_misconfigured():
        envelope = StructuredError(
            code="CORS_MISCONFIGURED",
            message=(
                "CORS_ALLOWED_ORIGINS is unset, empty, or unparseable; "
                "Admin_Backend will reject every cross-origin request "
                "with HTTP 403."
            ),
        )
        _log_structured_error(envelope)
        app.add_middleware(
            _DenyAllMiddleware,
            status_code=403,
            error_code="CORS_MISCONFIGURED",
            message=envelope.message,
        )
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _install_trusted_host_middleware(
    app: FastAPI, settings: Settings
) -> None:
    """Install ``TrustedHostMiddleware`` or its deny-all stand-in (R20.6 / R20.7)."""

    if settings.trusted_hosts_misconfigured():
        envelope = StructuredError(
            code="TRUSTED_HOSTS_MISCONFIGURED",
            message=(
                "TRUSTED_HOSTS is unset, empty, or unparseable; "
                "Admin_Backend will reject every incoming request "
                "with HTTP 400."
            ),
        )
        _log_structured_error(envelope)
        app.add_middleware(
            _DenyAllMiddleware,
            status_code=400,
            error_code="TRUSTED_HOSTS_MISCONFIGURED",
            message=envelope.message,
        )
        return

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(settings.trusted_hosts),
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _build_lifespan(
    *,
    settings: Settings | None,
    probe_fn_factory: ProbeFnFactory,
    breaker: CircuitBreaker | None = None,
) -> Callable[[FastAPI], Any]:
    """Build a lifespan coroutine bound to the given configuration.

    ``settings`` is captured so :func:`create_app` can pass a test
    instance through.  When ``None``, the lifespan re-reads the process
    env via :func:`get_settings` so production reloads pick up changes.

    ``probe_fn_factory`` builds the breaker probe coroutine; tests
    inject a mock factory to avoid real HTTP calls.

    ``breaker`` lets :func:`create_app` pass in a pre-built circuit
    breaker so observability hooks (task 10.5's ``langgraph_circuit_state``
    Prometheus gauge) can be wired up *before* the lifespan starts.
    When ``None``, the lifespan constructs a fresh breaker internally —
    this preserves the no-arg module-level ``lifespan`` symbol for
    callers that imported it from task 10.1.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ----- Settings (R14.1, R14.8) ---------------------------------
        try:
            resolved_settings = (
                settings if settings is not None else get_settings()
            )
        except LangGraphUpstreamConfigError as exc:
            # R14.8: emit the structured envelope **once** and re-raise
            # so ``uvicorn`` aborts before binding the HTTP port.
            _log_structured_error(exc.structured_error)
            raise

        # ----- Circuit breaker + LangGraph client (R14.4, R14.5) -------
        # Reuse the breaker built by :func:`create_app` so its
        # ``state_listeners`` (set up by ``setup_metrics`` for the
        # ``langgraph_circuit_state`` gauge) survive lifespan startup.
        # Fall back to a fresh breaker only when the lifespan was
        # constructed without one (the module-level ``lifespan`` symbol
        # exported for backwards compatibility).
        active_breaker = breaker if breaker is not None else CircuitBreaker()
        client = LangGraphClient(
            base_url=resolved_settings.langgraph_upstream_url,
            breaker=active_breaker,
        )

        probe_fn = probe_fn_factory(client)
        probe_task = asyncio.create_task(
            active_breaker.probe_loop(probe_fn),
            name="langgraph_probe_loop",
        )

        # Mount on app.state so request handlers (task 9.5 + future
        # routes) can reach the client/breaker via ``request.app.state``.
        app.state.settings = resolved_settings
        app.state.circuit_breaker = active_breaker
        app.state.langgraph_client = client
        app.state.langgraph_probe_task = probe_task

        try:
            yield
        finally:
            # ----- Shutdown (R14.4, R14.9) -----------------------------
            # Cancel the probe loop first so it does not try to call
            # ``on_failure`` after the client has been closed.
            probe_task.cancel()
            try:
                await probe_task
            except asyncio.CancelledError:
                # Expected on graceful shutdown.
                pass
            except Exception:  # noqa: BLE001 — log + swallow on shutdown
                logger.warning(
                    "langgraph.probe_task.shutdown_error",
                    exc_info=True,
                )

            try:
                await client.aclose()
            except Exception:  # noqa: BLE001 — log + swallow on shutdown
                logger.warning(
                    "langgraph.client.aclose_error",
                    exc_info=True,
                )

    return lifespan


# Re-export a no-arg lifespan symbol so ``from app.main import lifespan``
# keeps working for callers that imported it from task 10.1.  This
# instance reads settings lazily and uses the default probe factory.
lifespan = _build_lifespan(
    settings=None, probe_fn_factory=_build_default_probe_fn
)


def create_app(
    settings: Settings | None = None,
    *,
    probe_fn_factory: ProbeFnFactory | None = None,
) -> FastAPI:
    """Build a fresh FastAPI app shell with the hardening middlewares.

    Args:
        settings: Optional pre-built :class:`Settings`.  Tests inject
            this to exercise the four configuration permutations
            (CORS ok/bad × hosts ok/bad) without mutating
            ``os.environ``.  Production callers pass ``None`` and the
            factory loads via :func:`get_settings`.
        probe_fn_factory: Optional override that builds the breaker's
            probe coroutine from the constructed
            :class:`LangGraphClient`.  Defaults to
            :func:`_build_default_probe_fn`.  Tests inject a stub here
            so the breaker probe loop never makes real HTTP calls.

    Returns:
        A configured :class:`FastAPI` instance.  Routes are layered on
        top by subsequent tasks (9.5 / 10.5).
    """

    resolved_settings = settings if settings is not None else get_settings()
    factory = (
        probe_fn_factory
        if probe_fn_factory is not None
        else _build_default_probe_fn
    )

    # The breaker is constructed here (rather than inside the lifespan)
    # so observability wiring — task 10.5's ``langgraph_circuit_state``
    # Prometheus gauge — can attach a synchronous state listener
    # *before* the lifespan starts the probe loop.  The same instance
    # is reused by ``_build_lifespan`` to build the LangGraph client.
    breaker = CircuitBreaker()

    app = FastAPI(
        title="UIT Admin Dashboard API (app shell)",
        description=(
            "FastAPI shell introduced by the cicd-deploy-admin-dashboard "
            "spec.  Task 10.1 wires CORS + trusted-host hardening; "
            "task 9.4 wires the LangGraph upstream client + circuit "
            "breaker; subsequent tasks layer observability and "
            "authentication on top."
        ),
        version="0.1.0",
        lifespan=_build_lifespan(
            settings=resolved_settings,
            probe_fn_factory=factory,
            breaker=breaker,
        ),
    )

    # Starlette middlewares execute in reverse-add order (LIFO): the
    # *last* middleware added wraps every prior one and therefore runs
    # first on the request path.  Design C15 mandates that the
    # trusted-host check runs *before* CORS, so we add CORS first and
    # TrustedHost last.
    _install_cors_middleware(app, resolved_settings)
    _install_trusted_host_middleware(app, resolved_settings)

    # Routes (task 9.5).  ``/healthz`` is the docker-compose
    # healthcheck target (design C11), the smoke-test backend probe
    # (design C12), and the production deploy's post-rollout probe
    # (design C9).  The router is registered *before* metrics so the
    # instrumentator sees the route at install time.
    app.include_router(health_api.router)

    # Observability surface (design C13, R17.6, task 10.5).  Installed
    # *after* the hardening middlewares so it wraps them in Starlette's
    # LIFO middleware stack — every request, including the one that
    # gets rejected by ``TrustedHostMiddleware``, still flows through
    # the instrumentator and shows up in ``http_requests_total``.
    # Attaching the breaker's state listener here (rather than inside
    # the lifespan) guarantees the ``langgraph_circuit_state`` gauge is
    # populated before the first request can race the probe task.
    setup_metrics(app, breaker)

    return app


# Module-level FastAPI instance used by ``uvicorn app.main:app`` and by
# tests that rely on the default settings.  We attempt to construct
# from real environment values; if ``LANGGRAPH_UPSTREAM_URL`` is unset
# or invalid, we fall back to a placeholder so import-time failures do
# not mask the structured startup error.  The lifespan hook calls
# :func:`get_settings` again and re-raises the original
# :class:`LangGraphUpstreamConfigError` so ``uvicorn`` exits non-zero
# before binding the HTTP port (R14.8).
def _build_default_app() -> FastAPI:
    try:
        return create_app()
    except LangGraphUpstreamConfigError:
        placeholder = Settings(
            LANGGRAPH_UPSTREAM_URL=_PLACEHOLDER_UPSTREAM_URL,  # type: ignore[arg-type]
        )
        return create_app(settings=placeholder)


# Tests that need a custom settings instance should call ``create_app``
# directly rather than mutating ``app``.
app: FastAPI = _build_default_app()


__all__ = ["app", "create_app", "lifespan"]
