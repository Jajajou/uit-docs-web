"""Unit tests for ``app.core.security.set_auth_cookie`` (R20.3).

These tests cover the production / non-production branching of the
helper introduced by task 10.1.  The matching property test lives at
``tests/core/test_cookies.py`` (task 10.2).
"""

from __future__ import annotations

from http.cookies import SimpleCookie

import pytest
from starlette.responses import Response

from app.core.security import COOKIE_PATH, SAME_SITE_LAX, set_auth_cookie
from app.core.settings import Settings

VALID_URL = "https://langgraph.example.com"


def _build_settings(env: str) -> Settings:
    """Build a :class:`Settings` instance with ``ENV`` overridden.

    The other variables are stubbed so :class:`Settings` construction
    succeeds.  We do not exercise CORS/TRUSTED_HOSTS here.
    """

    return Settings(
        LANGGRAPH_UPSTREAM_URL=VALID_URL,  # type: ignore[arg-type]
        ENV=env,  # type: ignore[arg-type]
    )


def _parse_set_cookie(header: str) -> SimpleCookie:
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(header)
    return cookie


def _set_cookie_header(response: Response) -> str:
    header = response.headers.get("set-cookie")
    assert header is not None, "Response must carry a Set-Cookie header"
    return header


# ---------------------------------------------------------------------------
# Production branch (R20.3) — Secure must be present.
# ---------------------------------------------------------------------------


def test_production_cookie_has_full_attribute_set() -> None:
    settings = _build_settings("production")
    response = Response()

    set_auth_cookie(
        response,
        key="session",
        value="abc123",
        settings=settings,
    )

    header = _set_cookie_header(response)
    cookie = _parse_set_cookie(header)
    morsel = cookie["session"]

    assert morsel.value == "abc123"
    # Path is always /.
    assert morsel["path"] == COOKIE_PATH
    # Production must enable Secure.
    assert morsel["secure"] is True
    # HttpOnly is always set.
    assert morsel["httponly"] is True
    # SameSite=Lax is always set; SimpleCookie preserves the original
    # casing (``Lax``) we wrote out.
    assert morsel["samesite"].lower() == SAME_SITE_LAX


def test_production_secure_flag_appears_in_raw_header() -> None:
    """Defence-in-depth: spot-check the literal Set-Cookie header."""

    settings = _build_settings("production")
    response = Response()
    set_auth_cookie(response, "session", "v", settings)

    header = _set_cookie_header(response).lower()
    assert "secure" in header
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "path=/" in header


# ---------------------------------------------------------------------------
# Non-production branch — Secure must be absent so localhost works.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("env", ["dev", "staging", "test", "ci"])
def test_non_production_cookie_omits_secure(env: str) -> None:
    settings = _build_settings(env)
    response = Response()
    set_auth_cookie(response, "session", "v", settings)

    header = _set_cookie_header(response)
    cookie = _parse_set_cookie(header)
    morsel = cookie["session"]

    # Secure is dropped outside production.
    assert morsel["secure"] == ""
    # The remaining hardening attributes stay on for parity.
    assert morsel["httponly"] is True
    assert morsel["samesite"].lower() == SAME_SITE_LAX
    assert morsel["path"] == COOKIE_PATH

    # Raw header sanity check.
    lower = header.lower()
    assert "secure" not in lower.split(";")[0:1] + [
        seg.strip() for seg in lower.split(";")
    ] or "secure" not in lower
    assert "httponly" in lower
    assert "samesite=lax" in lower


# ---------------------------------------------------------------------------
# Forwarding of optional attributes
# ---------------------------------------------------------------------------


def test_max_age_is_forwarded() -> None:
    settings = _build_settings("production")
    response = Response()
    set_auth_cookie(response, "session", "v", settings, max_age=900)

    header = _set_cookie_header(response).lower()
    assert "max-age=900" in header


def test_domain_is_forwarded_when_provided() -> None:
    settings = _build_settings("production")
    response = Response()
    set_auth_cookie(
        response,
        "session",
        "v",
        settings,
        domain="admin.example.com",
    )

    header = _set_cookie_header(response).lower()
    assert "domain=admin.example.com" in header


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_key", ["", "   "])
def test_empty_key_rejected(bad_key: str) -> None:
    settings = _build_settings("production")
    response = Response()
    with pytest.raises(ValueError):
        set_auth_cookie(response, bad_key, "v", settings)
