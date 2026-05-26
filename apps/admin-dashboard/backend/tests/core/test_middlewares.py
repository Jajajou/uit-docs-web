"""Unit tests for the production-hardening middlewares (R20.4–R20.7).

These cover the four configuration permutations of CORS and trusted
hosts plus the structured-error logging side effect that task 10.1
introduces in ``app/main.py``.
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings, reset_settings_cache
from app.main import _DenyAllMiddleware, create_app  # type: ignore[attr-defined]

VALID_URL = "https://langgraph.example.com"
ALLOWED_ORIGIN = "https://admin.example.com"
ALLOWED_HOST = "admin.example.com"


@pytest.fixture(autouse=True)
def _ensure_lifespan_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ``LANGGRAPH_UPSTREAM_URL`` so the lifespan hook does not crash.

    The lifespan defined in :mod:`app.main` calls
    :func:`app.core.settings.get_settings` and lets the resulting
    :class:`LangGraphUpstreamConfigError` propagate (see task 9.4).
    These middleware tests do not exercise that error path; they need
    a valid env so ``TestClient`` can complete its lifespan handshake.
    """

    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    reset_settings_cache()


def _build_settings(
    *,
    cors: str = "",
    hosts: str = "",
    env: str = "production",
) -> Settings:
    return Settings(
        LANGGRAPH_UPSTREAM_URL=VALID_URL,  # type: ignore[arg-type]
        CORS_ALLOWED_ORIGINS=cors,  # type: ignore[arg-type]
        TRUSTED_HOSTS=hosts,  # type: ignore[arg-type]
        ENV=env,  # type: ignore[arg-type]
    )


def _build_app_and_client(settings: Settings):
    app = create_app(settings=settings)

    # Add a tiny ping route so a properly configured app has something
    # to serve.  This keeps the test focused on the middleware layer
    # without depending on the routes that later tasks will add.
    @app.get("/ping")
    def _ping() -> dict[str, str]:
        return {"status": "pong"}

    return app, TestClient(app, base_url=f"http://{ALLOWED_HOST}")


# ---------------------------------------------------------------------------
# Properly configured app (R20.4 / R20.6 happy path)
# ---------------------------------------------------------------------------


def test_allowed_origin_request_succeeds() -> None:
    settings = _build_settings(cors=ALLOWED_ORIGIN, hosts=ALLOWED_HOST)
    app, client = _build_app_and_client(settings)

    response = client.get(
        "/ping",
        headers={"origin": ALLOWED_ORIGIN, "host": ALLOWED_HOST},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "pong"}
    # CORS middleware echoes the allowed origin back.
    assert (
        response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    )


def test_disallowed_origin_does_not_get_cors_echo() -> None:
    """R20.4: requests from non-allow-listed origins must not receive
    the ``Access-Control-Allow-Origin`` header.

    Starlette's :class:`CORSMiddleware` does not reject the underlying
    request — that is handled by the browser — but it omits the CORS
    response header, which is sufficient for R20.4 because browsers
    enforce the policy.
    """

    settings = _build_settings(cors=ALLOWED_ORIGIN, hosts=ALLOWED_HOST)
    _, client = _build_app_and_client(settings)

    response = client.get(
        "/ping",
        headers={
            "origin": "https://evil.example.com",
            "host": ALLOWED_HOST,
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in {
        k.lower() for k in response.headers.keys()
    }


def test_disallowed_host_returns_400() -> None:
    """R20.6: a Host header outside ``TRUSTED_HOSTS`` is rejected with HTTP 400."""

    settings = _build_settings(cors=ALLOWED_ORIGIN, hosts=ALLOWED_HOST)
    app, _ = _build_app_and_client(settings)
    # Connect with a different Host header.
    with TestClient(app, base_url="http://evil.example.com") as client:
        response = client.get("/ping")
    assert response.status_code == 400


def test_trusted_host_runs_before_cors() -> None:
    """Design C15: bad Host header must be rejected even with allow-listed Origin.

    A ``Host`` header outside ``TRUSTED_HOSTS`` must yield HTTP 400 even
    when the request's ``Origin`` is in ``CORS_ALLOWED_ORIGINS``.
    """

    settings = _build_settings(cors=ALLOWED_ORIGIN, hosts=ALLOWED_HOST)
    app, _ = _build_app_and_client(settings)
    with TestClient(app, base_url="http://evil.example.com") as client:
        response = client.get("/ping", headers={"origin": ALLOWED_ORIGIN})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Misconfigured CORS (R20.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cors_raw", ["", "   ", ",,,"])
def test_deny_all_cors_returns_403(
    cors_raw: str, caplog: pytest.LogCaptureFixture
) -> None:
    settings = _build_settings(cors=cors_raw, hosts=ALLOWED_HOST)
    with caplog.at_level(logging.ERROR, logger="app.main"):
        app, client = _build_app_and_client(settings)

    response = client.get(
        "/ping", headers={"host": ALLOWED_HOST, "origin": ALLOWED_ORIGIN}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "CORS_MISCONFIGURED"
    assert body["message"]
    assert body["request_id"]
    assert body["timestamp"]


def test_deny_all_cors_logs_structured_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _build_settings(cors="", hosts=ALLOWED_HOST)
    with caplog.at_level(logging.ERROR, logger="app.main"):
        create_app(settings=settings)

    matching = [
        record
        for record in caplog.records
        if getattr(record, "structured_error", {}).get("code")
        == "CORS_MISCONFIGURED"
    ]
    assert matching, (
        "Expected a structured_error log entry with "
        "code=CORS_MISCONFIGURED"
    )
    payload = matching[0].structured_error  # type: ignore[attr-defined]
    assert payload["code"] == "CORS_MISCONFIGURED"
    assert payload["message"]
    assert payload["request_id"]


# ---------------------------------------------------------------------------
# Misconfigured TRUSTED_HOSTS (R20.7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hosts_raw", ["", "   ", ",,,"])
def test_deny_all_trusted_hosts_returns_400(hosts_raw: str) -> None:
    settings = _build_settings(cors=ALLOWED_ORIGIN, hosts=hosts_raw)
    app, client = _build_app_and_client(settings)

    response = client.get("/ping", headers={"host": ALLOWED_HOST})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "TRUSTED_HOSTS_MISCONFIGURED"
    assert body["message"]
    assert body["request_id"]
    assert body["timestamp"]


def test_deny_all_trusted_hosts_logs_structured_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _build_settings(cors=ALLOWED_ORIGIN, hosts="")
    with caplog.at_level(logging.ERROR, logger="app.main"):
        create_app(settings=settings)

    matching = [
        record
        for record in caplog.records
        if getattr(record, "structured_error", {}).get("code")
        == "TRUSTED_HOSTS_MISCONFIGURED"
    ]
    assert matching, (
        "Expected a structured_error log entry with "
        "code=TRUSTED_HOSTS_MISCONFIGURED"
    )


def test_misconfigured_trusted_hosts_takes_precedence_over_cors() -> None:
    """C15: trusted-host check runs before CORS even on misconfiguration.

    When both env vars are unparseable, the trusted-host deny-all
    middleware must run first and produce HTTP 400 (not the CORS 403).
    """

    settings = _build_settings(cors="", hosts="")
    app, client = _build_app_and_client(settings)

    response = client.get("/ping", headers={"host": ALLOWED_HOST})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "TRUSTED_HOSTS_MISCONFIGURED"


# ---------------------------------------------------------------------------
# Internal helpers — isolated check on the deny-all middleware contract.
# ---------------------------------------------------------------------------


def test_deny_all_middleware_response_envelope_shape() -> None:
    """Ensure the deny-all middleware's response body is a valid envelope."""

    sent_messages: list[dict] = []

    async def receive() -> dict:  # pragma: no cover - unused in deny-all path
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent_messages.append(message)

    middleware = _DenyAllMiddleware(
        app=lambda *_args, **_kwargs: None,  # type: ignore[arg-type]
        status_code=418,
        error_code="BAD_ARG",
        message="teapot",
    )

    import anyio

    async def _drive() -> None:
        await middleware(
            {"type": "http", "method": "GET", "path": "/"}, receive, send
        )

    anyio.run(_drive)

    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 418
    body = sent_messages[1]["body"]
    parsed = json.loads(body)
    assert parsed["code"] == "BAD_ARG"
    assert parsed["message"] == "teapot"
    assert parsed["request_id"]
    assert parsed["timestamp"]
