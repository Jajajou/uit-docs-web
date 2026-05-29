"""Security helpers for request headers, cookies, and lightweight rate limiting."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from api.config import settings
from api.errors import ApiServiceError

SECURITY_HEADERS = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    "referrer-policy": "strict-origin-when-cross-origin",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}


class InMemoryRateLimiter:
    """Small in-process limiter for sensitive auth routes."""

    def __init__(self) -> None:
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()

    def consume(self, *, key: str, limit: int, window_seconds: int, now: float | None = None) -> int | None:
        timestamp = monotonic() if now is None else now
        retry_after = max(window_seconds, 1)

        with self._lock:
            bucket = self._entries[key]
            cutoff = timestamp - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                oldest = bucket[0]
                return max(int(window_seconds - (timestamp - oldest)) + 1, 1)

            bucket.append(timestamp)
            return None


AUTH_RATE_LIMITER = InMemoryRateLimiter()


def get_request_identity(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def normalize_host(raw_host: str | None) -> str:
    value = (raw_host or "").strip().lower()
    if not value:
        return ""
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    return value.split(":", 1)[0]


def host_matches_pattern(host: str, pattern: str) -> bool:
    candidate = pattern.strip().lower()
    if not candidate:
        return False
    if candidate == "*":
        return True
    if candidate.startswith("*."):
        suffix = candidate[1:]
        return host.endswith(suffix) and host != suffix[1:]
    return host == candidate


def enforce_trusted_host(request: Request) -> None:
    if not settings.TRUSTED_HOSTS:
        return

    host = normalize_host(request.headers.get("host") or request.url.hostname)
    if host and any(host_matches_pattern(host, pattern) for pattern in settings.TRUSTED_HOSTS):
        return

    raise ApiServiceError(
        status_code=400,
        code="invalid_host_header",
        message="The request host is not allowed for this environment.",
    )


def get_request_scheme(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto
    return request.url.scheme.lower()


def build_https_redirect_response(request: Request) -> RedirectResponse | None:
    if not settings.FORCE_HTTPS_REDIRECT or get_request_scheme(request) == "https":
        return None

    return RedirectResponse(url=str(request.url.replace(scheme="https")), status_code=307)


def enforce_auth_rate_limit(request: Request, *, bucket: str) -> None:
    retry_after_seconds = AUTH_RATE_LIMITER.consume(
        key=f"{bucket}:{get_request_identity(request)}",
        limit=max(settings.AUTH_RATE_LIMIT_MAX_REQUESTS, 1),
        window_seconds=max(settings.AUTH_RATE_LIMIT_WINDOW_SECONDS, 1),
    )
    if retry_after_seconds is None:
        return

    raise ApiServiceError(
        status_code=429,
        code="rate_limited",
        message="Too many authentication requests. Please retry shortly.",
        details={"retryAfterSeconds": retry_after_seconds},
    )


def apply_security_headers(response: Response) -> Response:
    for header_name, header_value in SECURITY_HEADERS.items():
        response.headers.setdefault(header_name, header_value)
    return response


def build_session_cookie_settings() -> dict[str, object]:
    cookie_settings: dict[str, object] = {
        "httponly": True,
        "path": "/",
        "samesite": settings.SESSION_COOKIE_SAMESITE,
        "secure": settings.SESSION_COOKIE_SECURE,
    }
    if settings.SESSION_COOKIE_DOMAIN:
        cookie_settings["domain"] = settings.SESSION_COOKIE_DOMAIN
    return cookie_settings
