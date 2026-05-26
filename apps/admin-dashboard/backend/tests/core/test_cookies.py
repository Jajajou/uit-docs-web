"""Property-based test for production cookie hardening.

Property 15: Production Cookie Hardening.

**Validates: Requirements 20.3**

For every (cookie name, cookie value, env) triple drawn from the
hypothesis strategies below, the ``Set-Cookie`` header emitted by
:func:`app.core.security.set_auth_cookie` must satisfy:

* ``HttpOnly`` is always present.
* ``SameSite=Lax`` is always present.
* ``Path=/`` is always present.
* ``Secure`` is present **iff** ``ENV == "production"``.

The matching unit tests live in ``tests/core/test_security.py``
(task 10.1).  This file owns the property-test obligation declared by
task 10.2 and runs with ``max_examples=100``.

Strategy notes:

* Cookie name uses ``string.ascii_letters + string.digits + "_-"`` so
  every draw is a syntactically valid cookie name (no ``,``, ``;``,
  ``=`` or control characters).  The minimum length of 1 mirrors the
  ``ValueError`` guard on :func:`set_auth_cookie`.
* Cookie value uses the same conservative alphabet plus a few neutral
  punctuation characters.  We deliberately avoid ``;`` / ``,`` / ``"``
  / whitespace / control bytes so the round-trip through
  :class:`http.cookies.SimpleCookie` (used by both Starlette's
  serialiser and our parser) is unambiguous; the property under test
  is about *attributes*, not value preservation.
* Environment values are drawn from ``["production", "staging", "dev"]``
  exactly as the task description spells out.
"""

from __future__ import annotations

import string
from http.cookies import SimpleCookie

from hypothesis import given, settings
from hypothesis import strategies as st
from starlette.responses import Response

from app.core.security import COOKIE_PATH, SAME_SITE_LAX, set_auth_cookie
from app.core.settings import Settings

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_NAME_ALPHABET = string.ascii_letters + string.digits + "_-"
_VALUE_ALPHABET = string.ascii_letters + string.digits + "_-.~"

_VALID_UPSTREAM_URL = "https://langgraph.example.com"

_NAMES = st.text(alphabet=_NAME_ALPHABET, min_size=1, max_size=32)
_VALUES = st.text(alphabet=_VALUE_ALPHABET, min_size=1, max_size=100)
_ENVS = st.sampled_from(["production", "staging", "dev"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_settings(env: str) -> Settings:
    """Construct :class:`Settings` with a valid upstream URL and the env.

    A real upstream URL is required because :class:`Settings` raises
    :class:`~app.core.settings.LangGraphUpstreamConfigError` when it is
    unset/empty/malformed.  For this property we only care about the
    cookie branch, so we supply a placeholder URL that satisfies the
    validator.
    """

    return Settings(
        LANGGRAPH_UPSTREAM_URL=_VALID_UPSTREAM_URL,  # type: ignore[arg-type]
        ENV=env,  # type: ignore[arg-type]
    )


def _set_cookie_header(response: Response) -> str:
    header = response.headers.get("set-cookie")
    assert header is not None, "Response must carry a Set-Cookie header"
    return header


def _parse(header: str) -> SimpleCookie:
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(header)
    return cookie


# ---------------------------------------------------------------------------
# Property
# ---------------------------------------------------------------------------


@given(name=_NAMES, value=_VALUES, env=_ENVS)
@settings(max_examples=100)
def test_production_cookie_hardening(name: str, value: str, env: str) -> None:
    """**Validates: Requirements 20.3**

    For any cookie name / value / env tuple, the issued ``Set-Cookie``
    header must always carry ``HttpOnly``, ``SameSite=Lax`` and
    ``Path=/``; ``Secure`` must be present iff ``env == "production"``.
    """

    settings_obj = _build_settings(env)
    response = Response()

    set_auth_cookie(response, name, value, settings_obj)

    header = _set_cookie_header(response)
    cookie = _parse(header)

    # The morsel keyed by ``name`` must exist.  ``SimpleCookie`` lower-
    # cases nothing, so the key is preserved verbatim.
    assert name in cookie, (
        f"expected cookie {name!r} in parsed Set-Cookie, "
        f"got keys {list(cookie.keys())!r} for header {header!r}"
    )
    morsel = cookie[name]

    # --- Always-on attributes (defence in depth even outside prod). ---
    assert morsel["httponly"] is True, (
        f"HttpOnly must always be present (env={env!r}, header={header!r})"
    )
    assert morsel["samesite"].lower() == SAME_SITE_LAX, (
        f"SameSite must always equal {SAME_SITE_LAX!r} "
        f"(env={env!r}, got {morsel['samesite']!r}, header={header!r})"
    )
    assert morsel["path"] == COOKIE_PATH, (
        f"Path must always be {COOKIE_PATH!r} "
        f"(env={env!r}, got {morsel['path']!r}, header={header!r})"
    )

    # --- Secure flag iff production. ---
    secure_attr = morsel["secure"]
    secure_present = bool(secure_attr)
    expected_secure = env == "production"
    assert secure_present is expected_secure, (
        "Secure flag must be present iff env == 'production' "
        f"(env={env!r}, secure_present={secure_present!r}, "
        f"header={header!r})"
    )
