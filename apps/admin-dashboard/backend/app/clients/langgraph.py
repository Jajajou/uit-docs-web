"""LangGraph upstream HTTP client (design C10).

This module wires the :class:`~app.clients.circuit_breaker.CircuitBreaker`
state machine to a defensive ``httpx.AsyncClient`` that talks to
``LangGraph_Upstream``.  It is the single surface used by the FastAPI
app to call the upstream and is the place where Requirements 14.2,
14.3, 14.6, 14.9, 15.2 and 15.3 are realised:

* ``httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)``
  enforces R14.2.
* ``tenacity.AsyncRetrying`` with ``stop_after_attempt(3)`` and
  ``wait_exponential(multiplier=0.5, min=0.5, max=4.0)`` enforces R14.3
  (max 3 attempts, 500 ms..4 s backoff, retry only on connect errors,
  read/write/pool timeouts and HTTP 5xx — never on 4xx).
* The breaker is consulted **before every attempt** via
  :meth:`CircuitBreaker.allow_request`; an open breaker short-circuits
  with :class:`LangGraphUnavailable` and no upstream call is made
  (R14.4, R14.9).
* ``on_success`` / ``on_failure`` are awaited after every attempt so the
  rolling 60-second failure window stays accurate (R14.4).
* On retry exhaustion, :class:`LangGraphUnavailable` carries a
  :class:`~app.core.errors.Structured_Error` with
  ``code="LANGGRAPH_UNAVAILABLE"``, the **redacted** upstream URL,
  ``elapsed_ms`` (wall time of the *entire* retry budget measured via
  :func:`time.monotonic`) and ``request_id`` (R14.6, R14.9).

The module deliberately stays free of FastAPI imports — task 9.4 wires
the client into ``app.state`` from the FastAPI ``lifespan``.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.clients.circuit_breaker import CircuitBreaker
from app.core.errors import StructuredError, _new_request_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public configuration constants (mirror design C10 / R14.2, R14.3)
# ---------------------------------------------------------------------------

#: Connect timeout, in seconds (R14.2).
DEFAULT_CONNECT_TIMEOUT: Final[float] = 5.0

#: Read timeout, in seconds (R14.2).
DEFAULT_READ_TIMEOUT: Final[float] = 30.0

#: Write timeout, in seconds (R14.2).
DEFAULT_WRITE_TIMEOUT: Final[float] = 30.0

#: Pool acquisition timeout, in seconds (R14.2).
DEFAULT_POOL_TIMEOUT: Final[float] = 5.0

#: Maximum total attempts (1 original + 2 retries) per design C10 / R14.3.
DEFAULT_MAX_ATTEMPTS: Final[int] = 3

#: Exponential backoff multiplier (R14.3).
DEFAULT_RETRY_WAIT_MULTIPLIER: Final[float] = 0.5

#: Minimum retry delay, in seconds (R14.3 — 500 ms).
DEFAULT_RETRY_WAIT_MIN: Final[float] = 0.5

#: Maximum retry delay, in seconds (R14.3 — 4 seconds).
DEFAULT_RETRY_WAIT_MAX: Final[float] = 4.0

#: ``httpx`` exceptions that the design treats as retryable transport
#: failures.  ``ConnectTimeout``/``ReadTimeout``/``WriteTimeout``/
#: ``PoolTimeout`` are all subclasses of ``httpx.TimeoutException`` but
#: listed explicitly so the contract maps 1:1 to R14.3.  Note that
#: ``httpx.ConnectTimeout`` is **not** a subclass of
#: ``httpx.ConnectError`` — it is a sibling under
#: ``httpx.TimeoutException`` — so it must be enumerated explicitly or
#: connect timeouts will leak out of :meth:`LangGraphClient.request`
#: instead of being mapped to :class:`LangGraphUnavailable`.
_RETRYABLE_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LangGraphUnavailable(Exception):
    """Raised when the upstream cannot be reached within the retry budget.

    The exception carries the canonical
    :class:`~app.core.errors.Structured_Error` envelope
    (``code="LANGGRAPH_UNAVAILABLE"``) plus the redacted upstream URL
    and the wall-clock elapsed time so the FastAPI 503 handler (task
    9.5) can serialise the body without exposing the upstream
    response.

    Attributes:
        structured_error: The :class:`Structured_Error` envelope
            returned to the caller.
        redacted_url: Upstream URL with any ``user[:password]`` segment
            stripped via :func:`urllib.parse.urlsplit`.
        elapsed_ms: Wall-clock time (``time.monotonic``) of the *entire*
            retry budget, in integer milliseconds.
    """

    def __init__(
        self,
        *,
        structured_error: StructuredError,
        redacted_url: str,
        elapsed_ms: int,
    ) -> None:
        if structured_error.code != "LANGGRAPH_UNAVAILABLE":
            raise ValueError(
                "LangGraphUnavailable requires Structured_Error with "
                "code='LANGGRAPH_UNAVAILABLE', "
                f"got {structured_error.code!r}"
            )
        self.structured_error = structured_error
        self.redacted_url = redacted_url
        self.elapsed_ms = int(elapsed_ms)
        super().__init__(structured_error.message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def redact_url(url: str) -> str:
    """Return ``url`` with any ``user[:password]`` segment stripped.

    Implemented via :func:`urllib.parse.urlsplit` /
    :func:`urllib.parse.urlunsplit` so the output is always a
    syntactically valid URL when the input is.  Inputs that do not
    parse (or are empty) are returned unchanged — the caller is
    responsible for never printing raw bytes outside the structured
    log envelope.
    """

    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.hostname:
        # Nothing useful to rewrite — return the input untouched so
        # callers can still display the value in a log envelope.
        return url
    netloc = parts.hostname
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit(
        (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
    )


def _is_retryable_status(response: httpx.Response) -> bool:
    """Return ``True`` iff ``response.status_code`` is a retryable 5xx."""

    return 500 <= response.status_code < 600


def _build_default_timeout() -> httpx.Timeout:
    """Build the default :class:`httpx.Timeout` per R14.2."""

    return httpx.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT,
        read=DEFAULT_READ_TIMEOUT,
        write=DEFAULT_WRITE_TIMEOUT,
        pool=DEFAULT_POOL_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# Internal sentinel exception used to drive tenacity's retry loop on 5xx
# responses.  ``tenacity`` retries on exceptions; wrapping the response in
# a sentinel keeps the retry policy declarative (``retry_if_exception``)
# without leaking the response object via tenacity's ``retry_state.outcome``
# bookkeeping.
# ---------------------------------------------------------------------------


class _RetryableHttpStatus(Exception):
    """Internal sentinel raised by attempts returning a retryable 5xx."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        super().__init__(
            f"upstream returned retryable status {response.status_code}"
        )


def _is_retryable(exc: BaseException) -> bool:
    """``tenacity`` predicate: retry on transport errors and 5xx sentinel.

    Always returns ``False`` for :class:`LangGraphUnavailable` and
    :class:`httpx.HTTPStatusError` raised on 4xx responses so 4xx is
    never retried (R14.3).
    """

    if isinstance(exc, LangGraphUnavailable):
        return False
    if isinstance(exc, _RetryableHttpStatus):
        return True
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


# ---------------------------------------------------------------------------
# LangGraph client
# ---------------------------------------------------------------------------


class LangGraphClient:
    """Defensive HTTP client for ``LangGraph_Upstream`` (design C10).

    The constructor accepts either a fully constructed
    :class:`httpx.AsyncClient` (for tests / dependency injection) or
    builds one from :func:`_build_default_timeout` plus ``base_url``.

    Args:
        base_url: Upstream base URL; mounted on the underlying
            ``httpx.AsyncClient`` only when no client is injected.
        breaker: Circuit breaker that gates every attempt (R14.4).
        http_client: Optional injected ``httpx.AsyncClient``.  When
            ``None``, a new client is built with the design timeouts
            and is owned (closed by :meth:`aclose`).
        max_attempts: Override for the total number of attempts
            (default ``3``).  Tests use ``1`` to exercise the
            breaker-only path without retries.
        retry_wait_multiplier/_min/_max: Override for the
            ``wait_exponential`` parameters; tests pin them to ``0.0``
            for fast assertions on retry counts.
    """

    def __init__(
        self,
        base_url: str,
        breaker: CircuitBreaker,
        *,
        http_client: httpx.AsyncClient | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_wait_multiplier: float = DEFAULT_RETRY_WAIT_MULTIPLIER,
        retry_wait_min: float = DEFAULT_RETRY_WAIT_MIN,
        retry_wait_max: float = DEFAULT_RETRY_WAIT_MAX,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if not isinstance(breaker, CircuitBreaker):
            raise TypeError("breaker must be a CircuitBreaker instance")

        self._base_url = base_url
        self._breaker = breaker
        self._max_attempts = max_attempts
        self._retry_wait_multiplier = retry_wait_multiplier
        self._retry_wait_min = retry_wait_min
        self._retry_wait_max = retry_wait_max

        if http_client is None:
            self._http = httpx.AsyncClient(
                base_url=base_url,
                timeout=_build_default_timeout(),
            )
            self._owns_http = True
        else:
            self._http = http_client
            self._owns_http = False

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` if we own it.

        Injected clients (``http_client`` argument) are left alone so
        callers retain control of their lifetime.
        """

        if self._owns_http:
            await self._http.aclose()

    @property
    def base_url(self) -> str:
        """Configured upstream base URL (verbatim, not redacted)."""

        return self._base_url

    @property
    def breaker(self) -> CircuitBreaker:
        """The circuit breaker shared with ``app.state``."""

        return self._breaker

    # ------------------------------------------------------------------
    # Public request entry point
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> httpx.Response:
        """Issue an HTTP request to the LangGraph upstream.

        The call is wrapped in :class:`tenacity.AsyncRetrying` per
        R14.3.  The breaker is consulted before every attempt; an open
        breaker raises :class:`LangGraphUnavailable` immediately, and
        any upstream exception or 5xx response after retry exhaustion
        is mapped to the same exception.  4xx responses are returned
        verbatim — they are *not* breaker failures and *not* retried.

        Args:
            method: HTTP method (``"GET"``, ``"POST"`` …).
            path: Path appended to the configured base URL.  An
                absolute URL also works because ``httpx`` accepts
                either form.
            json: Optional JSON body.
            headers: Optional headers; merged with the request id when
                supplied.
            request_id: Caller-supplied identifier, used in the error
                envelope.  When ``None``, a fresh UUID is generated so
                the structured error is always populated (R14.6).

        Returns:
            The :class:`httpx.Response` for any 2xx or 4xx outcome.

        Raises:
            LangGraphUnavailable: When the breaker is open, every
                retry attempt fails, or the final attempt returns a
                5xx response.
        """

        effective_request_id = request_id or _new_request_id()
        request_headers: dict[str, str] = dict(headers or {})
        # Always forward the request id so the upstream can correlate
        # logs.  Existing values supplied by the caller win.
        request_headers.setdefault("X-Request-Id", effective_request_id)

        started_at = time.monotonic()
        last_exception: BaseException | None = None
        last_status: int | None = None

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential(
                    multiplier=self._retry_wait_multiplier,
                    min=self._retry_wait_min,
                    max=self._retry_wait_max,
                ),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
                before_sleep=self._before_sleep_log,
            ):
                with attempt:
                    if not self._breaker.allow_request():
                        # Short-circuit: do not even attempt the call.
                        # We raise LangGraphUnavailable directly so
                        # tenacity stops retrying immediately
                        # (the predicate above returns False for it).
                        raise self._build_unavailable(
                            request_id=effective_request_id,
                            elapsed_ms=self._elapsed_ms_since(started_at),
                            reason="circuit_open",
                            last_status=None,
                            last_exception=None,
                        )

                    try:
                        response = await self._http.request(
                            method,
                            path,
                            json=json,
                            headers=request_headers,
                        )
                    except _RETRYABLE_EXCEPTIONS as exc:
                        last_exception = exc
                        last_status = None
                        await self._breaker.on_failure()
                        raise

                    if _is_retryable_status(response):
                        last_exception = None
                        last_status = response.status_code
                        await self._breaker.on_failure()
                        raise _RetryableHttpStatus(response)

                    # 2xx or 4xx — the upstream IS responding so we
                    # treat the call as a breaker success.  4xx is
                    # business-level and never retried (R14.3).
                    await self._breaker.on_success()
                    return response
        except LangGraphUnavailable:
            # Breaker-open short-circuit (raised inside the loop) —
            # surface it verbatim.
            raise
        except _RetryableHttpStatus as exc:
            # Retries exhausted with the upstream still returning 5xx.
            raise self._build_unavailable(
                request_id=effective_request_id,
                elapsed_ms=self._elapsed_ms_since(started_at),
                reason="http_5xx",
                last_status=exc.response.status_code,
                last_exception=None,
            ) from exc
        except _RETRYABLE_EXCEPTIONS as exc:
            # Retries exhausted with a transport-level failure.
            raise self._build_unavailable(
                request_id=effective_request_id,
                elapsed_ms=self._elapsed_ms_since(started_at),
                reason=self._classify_transport_exception(exc),
                last_status=None,
                last_exception=exc,
            ) from exc
        except RetryError as exc:  # pragma: no cover — reraise=True bypasses
            # Defensive: in case ``reraise=True`` ever changes shape we
            # still surface a structured error.
            raise self._build_unavailable(
                request_id=effective_request_id,
                elapsed_ms=self._elapsed_ms_since(started_at),
                reason="retry_exhausted",
                last_status=last_status,
                last_exception=last_exception,
            ) from exc

        # ``AsyncRetrying`` always either yields a success (we returned
        # from inside the loop) or re-raises the last exception, so this
        # line is unreachable.  Defensive raise keeps the type checker
        # honest.
        raise self._build_unavailable(  # pragma: no cover - defensive
            request_id=effective_request_id,
            elapsed_ms=self._elapsed_ms_since(started_at),
            reason="unknown",
            last_status=last_status,
            last_exception=last_exception,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _elapsed_ms_since(started_at: float) -> int:
        """Wall-clock elapsed time in integer milliseconds."""

        return max(0, int((time.monotonic() - started_at) * 1000))

    @staticmethod
    def _classify_transport_exception(exc: BaseException) -> str:
        """Map a transport exception to a short human label."""

        # ``ConnectTimeout`` is a sibling of ``ConnectError`` under
        # ``TimeoutException`` — it is **not** a subclass of
        # ``ConnectError`` — so it has to be checked explicitly.
        if isinstance(exc, httpx.ConnectTimeout):
            return "connect_timeout"
        if isinstance(exc, httpx.ConnectError):
            return "connect_error"
        if isinstance(exc, httpx.ReadTimeout):
            return "read_timeout"
        if isinstance(exc, httpx.WriteTimeout):
            return "write_timeout"
        if isinstance(exc, httpx.PoolTimeout):
            return "pool_timeout"
        return "transport_error"

    def _build_unavailable(
        self,
        *,
        request_id: str,
        elapsed_ms: int,
        reason: str,
        last_status: int | None,
        last_exception: BaseException | None,
    ) -> LangGraphUnavailable:
        """Construct a :class:`LangGraphUnavailable` with full context.

        The structured log emission is wrapped in ``try/except`` so a
        logging failure cannot leak the upstream body to the client
        (R14.6).
        """

        redacted = redact_url(self._base_url)
        if reason == "circuit_open":
            message = (
                "LangGraph circuit breaker is open; refusing upstream call."
            )
        elif reason == "http_5xx":
            message = (
                "LangGraph upstream returned a 5xx response after retries "
                "were exhausted."
            )
        elif reason == "connect_error":
            message = "LangGraph upstream connection error after retries."
        elif reason in {
            "connect_timeout",
            "read_timeout",
            "write_timeout",
            "pool_timeout",
            "transport_error",
        }:
            message = (
                "LangGraph upstream request timed out after retries."
            )
        else:
            message = "LangGraph upstream did not respond within retry budget."

        structured = StructuredError(
            code="LANGGRAPH_UNAVAILABLE",
            message=message,
            request_id=request_id,
        )

        try:
            logger.warning(
                "langgraph.unavailable",
                extra={
                    "code": structured.code,
                    "redacted_upstream_url": redacted,
                    "elapsed_ms": elapsed_ms,
                    "request_id": request_id,
                    "reason": reason,
                    "last_status": last_status,
                    "last_exception": (
                        type(last_exception).__name__
                        if last_exception is not None
                        else None
                    ),
                },
            )
        except Exception:  # noqa: BLE001 — never let logging failures leak
            pass

        return LangGraphUnavailable(
            structured_error=structured,
            redacted_url=redacted,
            elapsed_ms=elapsed_ms,
        )

    def _before_sleep_log(self, retry_state: RetryCallState) -> None:
        """Log a structured warning between retry attempts."""

        try:
            outcome = retry_state.outcome
            failure_repr: str | None
            if outcome is not None and outcome.failed:
                exc = outcome.exception()
                failure_repr = type(exc).__name__ if exc is not None else None
            else:
                failure_repr = None
            next_sleep = (
                retry_state.next_action.sleep
                if retry_state.next_action is not None
                else None
            )
            logger.warning(
                "langgraph.retry",
                extra={
                    "attempt_number": retry_state.attempt_number,
                    "next_sleep_seconds": next_sleep,
                    "failure": failure_repr,
                },
            )
        except Exception:  # noqa: BLE001 — logging must never raise
            pass


__all__ = [
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_POOL_TIMEOUT",
    "DEFAULT_READ_TIMEOUT",
    "DEFAULT_RETRY_WAIT_MAX",
    "DEFAULT_RETRY_WAIT_MIN",
    "DEFAULT_RETRY_WAIT_MULTIPLIER",
    "DEFAULT_WRITE_TIMEOUT",
    "LangGraphClient",
    "LangGraphUnavailable",
    "redact_url",
]
