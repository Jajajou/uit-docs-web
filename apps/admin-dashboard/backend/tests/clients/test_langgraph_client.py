"""Unit tests for ``app.clients.langgraph.LangGraphClient`` (task 9.3).

These tests cover the contract called out by Requirements 14.2, 14.3,
14.6, 14.9, 15.2 and 15.3:

* 2xx responses are returned verbatim and the breaker observes a single
  success.
* 4xx responses are returned without retrying and without affecting the
  breaker negatively (the upstream IS responding so we treat the call
  as a breaker success per design — only network or 5xx failures count
  toward the rolling failure window).
* Three consecutive 5xx responses exhaust the retry budget, raise
  :class:`LangGraphUnavailable` and increment the breaker failure
  counter exactly three times.
* Three consecutive ``httpx.ConnectError`` exceptions are also retried
  three times before raising.
* When the breaker is already ``Open``, ``request`` short-circuits
  immediately and never touches ``httpx``.
* The structured error envelope strips ``user:password`` segments from
  the upstream URL.
"""

from __future__ import annotations

from typing import Iterator
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.clients.circuit_breaker import BreakerState, CircuitBreaker
from app.clients.langgraph import (
    DEFAULT_MAX_ATTEMPTS,
    LangGraphClient,
    LangGraphUnavailable,
    redact_url,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


BASE_URL = "https://upstream.test"


def make_breaker(*, failure_threshold: int = 5) -> CircuitBreaker:
    return CircuitBreaker(failure_threshold=failure_threshold)


def make_client(
    *,
    breaker: CircuitBreaker,
    base_url: str = BASE_URL,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> LangGraphClient:
    """Build a :class:`LangGraphClient` with retry waits pinned to zero.

    Pinning the wait config keeps the failing-path tests sub-second and
    means we can assert exact attempt counts without timing flakiness.
    The retry policy itself is still exercised through tenacity.
    """

    return LangGraphClient(
        base_url,
        breaker,
        max_attempts=max_attempts,
        retry_wait_multiplier=0.0,
        retry_wait_min=0.0,
        retry_wait_max=0.0,
    )


@pytest.fixture
def spy_breaker() -> Iterator[CircuitBreaker]:
    """A breaker whose ``on_success``/``on_failure`` are AsyncMock-spied.

    The spies preserve the real state-machine behaviour by delegating
    to the original coroutines so tests can both assert call counts
    and observe state transitions.
    """

    breaker = make_breaker()
    original_on_success = breaker.on_success
    original_on_failure = breaker.on_failure

    success_spy = AsyncMock(side_effect=original_on_success)
    failure_spy = AsyncMock(side_effect=original_on_failure)
    breaker.on_success = success_spy  # type: ignore[method-assign]
    breaker.on_failure = failure_spy  # type: ignore[method-assign]
    yield breaker


# ---------------------------------------------------------------------------
# 2xx happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_2xx_returns_response_and_marks_success(spy_breaker: CircuitBreaker) -> None:
    client = make_client(breaker=spy_breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            route = router.get("/threads").mock(
                return_value=httpx.Response(200, json={"id": "abc"})
            )

            response = await client.request("GET", "/threads")

            assert response.status_code == 200
            assert response.json() == {"id": "abc"}
            assert route.call_count == 1

        spy_breaker.on_success.assert_awaited_once()  # type: ignore[attr-defined]
        spy_breaker.on_failure.assert_not_awaited()  # type: ignore[attr-defined]
        assert spy_breaker.state == BreakerState.CLOSED
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_request_id_is_forwarded_when_caller_supplies_one() -> None:
    breaker = make_breaker()
    client = make_client(breaker=breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            route = router.post("/threads").mock(
                return_value=httpx.Response(200, json={})
            )

            await client.request(
                "POST",
                "/threads",
                json={"hello": "world"},
                request_id="caller-rid-001",
            )

            request = route.calls.last.request
            assert request.headers.get("X-Request-Id") == "caller-rid-001"
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# 4xx is never retried
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_4xx_returns_response_without_retrying(
    spy_breaker: CircuitBreaker,
) -> None:
    client = make_client(breaker=spy_breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            route = router.post("/threads").mock(
                return_value=httpx.Response(404, json={"detail": "not found"})
            )

            response = await client.request("POST", "/threads", json={})

            assert response.status_code == 404
            # 4xx must never trigger a retry — exactly one upstream
            # call regardless of the retry budget.
            assert route.call_count == 1

        # The upstream IS responding, so the call counts as a breaker
        # success per design (only transport errors and 5xx feed the
        # rolling failure window).
        spy_breaker.on_success.assert_awaited_once()  # type: ignore[attr-defined]
        spy_breaker.on_failure.assert_not_awaited()  # type: ignore[attr-defined]
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# 5xx exhausts retries and raises LangGraphUnavailable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_5xx_three_times_raises_unavailable_after_three_attempts(
    spy_breaker: CircuitBreaker,
) -> None:
    client = make_client(breaker=spy_breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            route = router.get("/threads").mock(
                return_value=httpx.Response(503, text="upstream is down")
            )

            with pytest.raises(LangGraphUnavailable) as exc_info:
                await client.request("GET", "/threads")

            assert route.call_count == DEFAULT_MAX_ATTEMPTS

        err = exc_info.value
        assert err.structured_error.code == "LANGGRAPH_UNAVAILABLE"
        assert err.structured_error.request_id  # always populated
        assert err.elapsed_ms >= 0
        assert err.redacted_url == BASE_URL  # no credentials to strip

        # One on_failure per attempt; no successes.
        assert spy_breaker.on_failure.await_count == DEFAULT_MAX_ATTEMPTS  # type: ignore[attr-defined]
        spy_breaker.on_success.assert_not_awaited()  # type: ignore[attr-defined]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_5xx_response_body_does_not_leak_into_structured_error() -> None:
    """The 503 envelope must not echo the raw upstream body (R14.6)."""

    breaker = make_breaker()
    client = make_client(breaker=breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            router.get("/threads").mock(
                return_value=httpx.Response(500, text="SECRET_LEAK_TOKEN")
            )

            with pytest.raises(LangGraphUnavailable) as exc_info:
                await client.request("GET", "/threads")

        body = exc_info.value.structured_error.message
        assert "SECRET_LEAK_TOKEN" not in body
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Connect error exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_error_three_times_raises_unavailable(
    spy_breaker: CircuitBreaker,
) -> None:
    client = make_client(breaker=spy_breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            route = router.get("/threads").mock(
                side_effect=httpx.ConnectError("dns refused")
            )

            with pytest.raises(LangGraphUnavailable) as exc_info:
                await client.request("GET", "/threads")

            assert route.call_count == DEFAULT_MAX_ATTEMPTS

        err = exc_info.value
        assert err.structured_error.code == "LANGGRAPH_UNAVAILABLE"
        assert err.elapsed_ms >= 0

        assert spy_breaker.on_failure.await_count == DEFAULT_MAX_ATTEMPTS  # type: ignore[attr-defined]
        spy_breaker.on_success.assert_not_awaited()  # type: ignore[attr-defined]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_read_timeout_is_retried_then_raises(
    spy_breaker: CircuitBreaker,
) -> None:
    client = make_client(breaker=spy_breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            route = router.get("/threads").mock(
                side_effect=httpx.ReadTimeout("read timed out")
            )

            with pytest.raises(LangGraphUnavailable):
                await client.request("GET", "/threads")

            assert route.call_count == DEFAULT_MAX_ATTEMPTS
        assert spy_breaker.on_failure.await_count == DEFAULT_MAX_ATTEMPTS  # type: ignore[attr-defined]
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Mixed retry path: transient 5xx then 2xx succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_5xx_then_2xx_succeeds_within_budget(
    spy_breaker: CircuitBreaker,
) -> None:
    client = make_client(breaker=spy_breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            route = router.get("/threads").mock(
                side_effect=[
                    httpx.Response(502),
                    httpx.Response(200, json={"ok": True}),
                ]
            )

            response = await client.request("GET", "/threads")

        assert response.status_code == 200
        assert route.call_count == 2

        # One failure (the 502) and one success (the final 200).
        assert spy_breaker.on_failure.await_count == 1  # type: ignore[attr-defined]
        assert spy_breaker.on_success.await_count == 1  # type: ignore[attr-defined]
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Open breaker short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_breaker_raises_immediately_without_attempt() -> None:
    breaker = make_breaker()
    # Drive the breaker into Open without any HTTP traffic.
    for _ in range(breaker.failure_threshold):
        await breaker.on_failure()
    assert breaker.state == BreakerState.OPEN

    client = make_client(breaker=breaker)
    try:
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            route = router.get("/threads").mock(
                return_value=httpx.Response(200, json={})
            )

            with pytest.raises(LangGraphUnavailable) as exc_info:
                await client.request("GET", "/threads")

            # The HTTP route must never be touched when the breaker is
            # open — the client short-circuits before even creating
            # the request.
            assert route.call_count == 0

        err = exc_info.value
        assert err.structured_error.code == "LANGGRAPH_UNAVAILABLE"
        assert "circuit" in err.structured_error.message.lower()
        assert err.elapsed_ms >= 0
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# URL redaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_url_redaction_strips_credentials() -> None:
    breaker = make_breaker()
    client = make_client(
        breaker=breaker,
        base_url="https://user:pass@example.com/api",
    )
    try:
        # Configure respx to reject every call with a connection error so
        # we can read back the redacted URL from the resulting envelope.
        with respx.mock(base_url="https://example.com/api") as router:
            router.get("/threads").mock(
                side_effect=httpx.ConnectError("nope")
            )

            with pytest.raises(LangGraphUnavailable) as exc_info:
                await client.request("GET", "/threads")

        err = exc_info.value
        assert err.redacted_url == "https://example.com/api"
        assert "user" not in err.redacted_url
        assert "pass" not in err.redacted_url
    finally:
        await client.aclose()


def test_redact_url_helper_handles_common_inputs() -> None:
    assert redact_url("https://user:pass@example.com/api") == (
        "https://example.com/api"
    )
    assert redact_url("https://example.com/api") == "https://example.com/api"
    assert redact_url("https://user@example.com:9000/api") == (
        "https://example.com:9000/api"
    )
    assert redact_url("") == ""


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


def test_constructor_rejects_invalid_max_attempts() -> None:
    breaker = make_breaker()
    with pytest.raises(ValueError):
        LangGraphClient(BASE_URL, breaker, max_attempts=0)


def test_constructor_rejects_non_breaker() -> None:
    with pytest.raises(TypeError):
        LangGraphClient(BASE_URL, breaker=object())  # type: ignore[arg-type]


def test_unavailable_constructor_rejects_other_codes() -> None:
    from app.core.errors import StructuredError

    bad = StructuredError(code="BAD_ARG", message="nope")
    with pytest.raises(ValueError):
        LangGraphUnavailable(
            structured_error=bad,
            redacted_url="https://example.com",
            elapsed_ms=0,
        )
