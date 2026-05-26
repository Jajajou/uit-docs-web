"""Authentication-cookie hardening helpers (design C15, R20.3).

This module exposes :func:`set_auth_cookie`, a thin wrapper around
:meth:`starlette.responses.Response.set_cookie` that enforces the
production cookie attributes mandated by Requirement 20.3:

* ``Secure`` — set when :meth:`Settings.is_production` is ``True`` so
  the browser only sends the cookie over HTTPS.
* ``HttpOnly`` — always set; authentication cookies must not be visible
  to JavaScript (defence in depth even outside production).
* ``SameSite=Lax`` — always set; mitigates cross-site request forgery
  while preserving top-level navigation flows.
* ``Path=/`` — always set; the cookie is scoped to the entire backend.

Outside production we deliberately leave ``Secure`` off so the cookie
still works against ``http://localhost``-style developer setups.  The
remaining attributes are kept on at all times so dev cookies do not
diverge in shape from the production envelope.

The function is intentionally minimal — callers that need rotation,
deletion, or session-specific options should still go through
``response.delete_cookie`` / ``response.set_cookie`` directly.  This
helper exists only for the **issuance** path described in R20.3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from starlette.responses import Response

from .settings import Settings

# ---------------------------------------------------------------------------
# Constants — the hardened attribute set (design C15).
# ---------------------------------------------------------------------------

#: ``SameSite`` value used by :func:`set_auth_cookie` (R20.3).
SAME_SITE_LAX: Literal["lax"] = "lax"

#: Cookie path scope used by :func:`set_auth_cookie` (R20.3).
COOKIE_PATH: str = "/"


def set_auth_cookie(
    response: Response,
    key: str,
    value: str,
    settings: Settings,
    *,
    max_age: int | None = None,
    expires: int | str | datetime | None = None,
    domain: str | None = None,
) -> None:
    """Issue an authentication cookie with the hardened attribute set.

    Args:
        response: A Starlette/FastAPI :class:`Response` (or subclass)
            that the caller will eventually return to the client.
        key: Cookie name; must be a non-empty string.
        value: Cookie value; the caller is responsible for any signing
            or encoding.
        settings: Loaded :class:`Settings` instance used to decide
            whether the ``Secure`` flag should be set.
        max_age: Optional ``Max-Age`` in seconds, forwarded verbatim to
            :meth:`Response.set_cookie`.
        expires: Optional ``Expires`` value; same forwarding rules.
        domain: Optional ``Domain`` attribute; forwarded as-is.  Most
            callers should leave this unset so the cookie is scoped to
            the issuing host.

    Raises:
        ValueError: When ``key`` is empty or whitespace-only.
    """

    if not key or not key.strip():
        raise ValueError("auth cookie key must be a non-empty string")

    secure = settings.is_production()

    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        expires=expires,
        path=COOKIE_PATH,
        domain=domain,
        secure=secure,
        httponly=True,
        samesite=SAME_SITE_LAX,
    )


__all__ = [
    "COOKIE_PATH",
    "SAME_SITE_LAX",
    "set_auth_cookie",
]
