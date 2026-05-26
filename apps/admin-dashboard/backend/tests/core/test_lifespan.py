"""Unit tests for the FastAPI ``lifespan`` wiring (task 9.4).

The lifespan defined in :mod:`app.main` must, on startup:

* Read settings via :func:`app.core.settings.get_settings` and let
  :class:`LangGraphUpstreamConfigError` propagate (R14.1, R14.8).
* Instantiate a :class:`~app.clients.circuit_breaker.CircuitBreaker`
  and a :class:`~app.clients.langgraph.LangGraphClient` and mount them
  on ``app.state`` so request handlers can reach them (R14.4, R14.9).
* Spawn the breaker's probe loop as an :class:`asyncio.Task` and store
  the task on ``app.state.langgraph_probe_task`` (R14.5).

…and on shutdown:

* Cancel the probe task and await it, swallowing
  :class:`asyncio.CancelledError`.
* Close the LangGraph client via :meth:`LangGraphClient.aclose`.

These tests exercise the wiring with an injected probe factory so no
real HTTP traffic is generated.

**Validates: Requirements 14.1, 14.4, 14.5, 14.6, 14.9**
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import pytest
from fastapi.testclient import TestClient

from app.clients.circuit_breaker import CircuitBreaker, ProbeResult
from app.clients.langgraph import LangGraphClient
from app.core.settings import (
    LangGraphUpstreamConfigError,
    Settings,
    reset_settings_cache,
)
from app.main import (
    _build_default_probe_fn,
    _build_lifespan,
    create_app,
)

VALID_URL = "https://langgraph.example.com"
ALLOWED_ORIGIN = "https://admin.example.com"
ALLOWED_HOST = "admin.example.com"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Ensure each test sees a freshly-loaded :class:`Settings`."""

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
    """Build a probe-factory stub that never makes real HTTP calls.

    The returned factory ignores the :class:`LangGraphClient` it
    receives and produces a coroutine that returns ``return_value``
    immediately.  The coroutine yields control once via
    :func:`asyncio.sleep(0)` so the breaker's probe loop can be
    exercised by tests that rely on cooperative scheduling.
    """

    async def _probe() -> ProbeResult:
        await asyncio.sleep(0)
        return return_value

    def factory(_client: LangGraphClient) -> Callable[[], Awaitable[ProbeResult]]:
        return _probe

    return factory


# ---------------------------------------------------------------------------
# Happy path: startup mounts state, shutdown cleans up
# ---------------------------------------------------------------------------


def test_lifespan_mounts_client_and_breaker_on_app_state() -> None:
    """R14.1 + R14.4: after startup, ``app.state`` carries the breaker
    and the LangGraph client so request handlers can reach them."""

    settings = _build_settings()
    app = create_app(
        settings=settings, probe_fn_factory=_stub_probe_factory(200)
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}"):
        assert isinstance(app.state.circuit_breaker, CircuitBreaker)
        assert isinstance(app.state.langgraph_client, LangGraphClient)
        # The client must be configured against the same upstream URL
        # that ``Settings`` parsed (R14.1).
        assert app.state.langgraph_client.base_url == VALID_URL
        # The breaker is shared between the client and ``app.state``
        # so probes update the same state machine (R14.4).
        assert (
            app.state.langgraph_client.breaker is app.state.circuit_breaker
        )


def test_lifespan_spawns_probe_task() -> None:
    """R14.5: the probe loop is started as an asyncio task so the
    breaker can probe ``LangGraph_Upstream`` every 30s while open."""

    settings = _build_settings()
    app = create_app(
        settings=settings, probe_fn_factory=_stub_probe_factory(200)
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}"):
        task = app.state.langgraph_probe_task
        assert isinstance(task, asyncio.Task)
        assert not task.done(), "probe task must be running during lifespan"
        assert task.get_name() == "langgraph_probe_loop"


def test_lifespan_cancels_probe_task_and_closes_client_on_shutdown() -> None:
    """R14.4 + R14.9: shutdown cancels the probe task, awaits it, and
    closes the underlying ``httpx.AsyncClient`` so no resources leak."""

    settings = _build_settings()
    app = create_app(
        settings=settings, probe_fn_factory=_stub_probe_factory(200)
    )

    with TestClient(app, base_url=f"http://{ALLOWED_HOST}"):
        client = app.state.langgraph_client
        task = app.state.langgraph_probe_task

    # After the TestClient context exits, the lifespan shutdown must
    # have finalised the probe task.  Cancellation may surface as a
    # cancelled task or as a clean exit (the probe loop logs and
    # re-raises CancelledError).
    assert task.done(), "probe task must be finalised on shutdown"
    if not task.cancelled():
        exc = task.exception()
        assert exc is None or isinstance(exc, asyncio.CancelledError)

    # ``httpx.AsyncClient.is_closed`` becomes True only after the
    # close coroutine has run, which is exactly what the lifespan
    # shutdown branch must guarantee (R14.9).
    assert client._http.is_closed, (  # type: ignore[attr-defined]
        "LangGraph httpx client must be closed on shutdown"
    )


# ---------------------------------------------------------------------------
# Failure path: invalid LANGGRAPH_UPSTREAM_URL aborts startup (R14.8)
# ---------------------------------------------------------------------------


def test_lifespan_logs_and_reraises_config_error_on_startup(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """R14.6 + R14.8: when ``LANGGRAPH_UPSTREAM_URL`` is invalid the
    lifespan logs the structured envelope and re-raises so ``uvicorn``
    exits non-zero before binding the HTTP port."""

    # Drive the lifespan directly so we exercise the no-args branch
    # that calls :func:`get_settings` from the process env.  Using the
    # context manager rather than ``TestClient`` keeps the assertion
    # focused on the lifespan behaviour and avoids any TestClient
    # error wrapping.
    monkeypatch.delenv("LANGGRAPH_UPSTREAM_URL", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", ALLOWED_ORIGIN)
    monkeypatch.setenv("TRUSTED_HOSTS", ALLOWED_HOST)
    reset_settings_cache()

    failing_lifespan = _build_lifespan(
        settings=None, probe_fn_factory=_build_default_probe_fn
    )

    # A bare object with a ``state`` attribute is enough — the lifespan
    # only sets attributes on it before raising.
    class _FakeApp:
        class state:  # noqa: D401, N801 — match starlette's app.state shape
            pass

    async def _drive() -> None:
        async with failing_lifespan(_FakeApp()):  # type: ignore[arg-type]
            pass  # pragma: no cover — must not reach here

    with caplog.at_level(logging.ERROR, logger="app.main"):
        with pytest.raises(LangGraphUpstreamConfigError):
            asyncio.run(_drive())

    matching = [
        record
        for record in caplog.records
        if getattr(record, "structured_error", {}).get("code")
        == "LANGGRAPH_UPSTREAM_URL_MISSING"
    ]
    assert matching, (
        "Expected a structured_error log entry with "
        "code=LANGGRAPH_UPSTREAM_URL_MISSING"
    )


# ---------------------------------------------------------------------------
# Default probe factory returns a coroutine without making HTTP calls
# until awaited.
# ---------------------------------------------------------------------------


def test_default_probe_factory_returns_awaitable_without_io() -> None:
    """The default probe factory must produce an async callable so the
    breaker's ``probe_loop`` can schedule it.  Calling the factory
    must not perform any I/O until the resulting coroutine is awaited.
    """

    async def _check() -> None:
        breaker = CircuitBreaker()
        client = LangGraphClient(base_url=VALID_URL, breaker=breaker)
        try:
            probe = _build_default_probe_fn(client)
            assert callable(probe)
            coro = probe()
            try:
                assert asyncio.iscoroutine(coro)
            finally:
                coro.close()
        finally:
            await client.aclose()

    asyncio.run(_check())
