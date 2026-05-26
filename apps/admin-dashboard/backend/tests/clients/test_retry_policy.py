"""Property-based test for the LangGraph retry policy (task 9.7).

Property 9: LangGraph Retry Policy.

**Validates: Requirements 14.3, 14.4, 14.5**

For any finite sequence of upstream response outcomes
``R = (r_1, r_2, ...)`` where each ``r_i`` is drawn from
``{"2xx", "4xx", "5xx", "conn_error", "timeout"}``, a single
:meth:`app.clients.langgraph.LangGraphClient.request` call SHALL:

* (a) issue **at most 3 attempts** (1 original + 2 retries);
* (b) terminate immediately on the **first 2xx** or **any 4xx**;
* (c) retry **only** when the latest outcome is one of
  ``{5xx, conn_error, timeout}``;
* (d) place a delay between attempts drawn from the closed range
  ``[500ms, 4000ms]`` following exponential backoff with multiplier
  ``2`` (the design uses :class:`tenacity.wait_exponential`); and

Additionally, when the breaker is closed and 5 or more failures occur
within any rolling 60-second window, the breaker SHALL transition to
``Open`` (Requirement 14.4).

Strategy
--------
* The Hypothesis strategy is
  ``lists(sampled_from(["2xx","4xx","5xx","conn_error","timeout"]),
  min_size=1, max_size=10)``.  For every drawn sequence we cycle
  through it as the ``respx`` route's ``side_effect`` so the route
  never exhausts even when the sequence is shorter than the retry
  budget.
* Retry waits are pinned to ``0`` for the property body via the
  ``retry_wait_*`` constructor knobs documented in
  :mod:`app.clients.langgraph`; this keeps each Hypothesis example
  sub-second while still exercising the full ``tenacity.AsyncRetrying``
  loop (the wait callable is invoked even when its result is ``0``).
* A fresh :class:`CircuitBreaker` and :class:`LangGraphClient` are
  built per example so breaker state cannot leak between Hypothesis
  draws.
* The two non-property assertions called out by the task description
  -- the ``[500ms, 4000ms]`` delay range and the
  ``≥5 failures within 60s`` breaker transition -- live in dedicated
  unit tests below the property body.  Both run against a real
  :class:`CircuitBreaker` with default thresholds; the delay test
  records the exponential values via a wait-callable wrapper so it
  asserts on the real :class:`tenacity.wait_exponential` output
  without paying its real wall-clock cost.

Run from ``web/apps/admin-dashboard/backend``::

    pytest tests/clients/test_retry_policy.py -v
"""

from __future__ import annotations

import asyncio
from typing import Iterable, List, Optional, Tuple

import httpx
import pytest
import respx
from hypothesis import HealthCheck, given, settings as hypo_settings
from hypothesis import strategies as st

import app.clients.langgraph as langgraph_module
from app.clients.circuit_breaker import BreakerState, CircuitBreaker
from app.clients.langgraph import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRY_WAIT_MAX,
    DEFAULT_RETRY_WAIT_MIN,
    DEFAULT_RETRY_WAIT_MULTIPLIER,
    LangGraphClient,
    LangGraphUnavailable,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


BASE_URL = "https://upstream.test"

#: The five outcome labels enumerated by Property 9.  Order is fixed
#: so Hypothesis' shrinker reports counter-examples in a stable form.
OUTCOME_LABELS: Tuple[str, ...] = (
    "2xx",
    "4xx",
    "5xx",
    "conn_error",
    "timeout",
)

#: Outcomes that terminate the retry loop immediately (Property 9 (b)).
_TERMINAL_LABELS = frozenset({"2xx", "4xx"})

#: Outcomes that the retry policy must retry on (Property 9 (c)).
_RETRYABLE_LABELS = frozenset({"5xx", "conn_error", "timeout"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _label_to_side_effect(label: str) -> object:
    """Map a Hypothesis label to a ``respx``-compatible side effect.

    ``respx`` accepts either an :class:`httpx.Response` (returned as
    the route response) or an :class:`httpx.HTTPError` instance
    (re-raised inside the transport).  Mixing the two shapes inside a
    single ``side_effect`` list is supported and is the cleanest way
    to drive the property because we want to model both response-based
    and transport-based outcomes in the same sequence.
    """

    if label == "2xx":
        return httpx.Response(200, json={"ok": True})
    if label == "4xx":
        return httpx.Response(404, json={"detail": "not found"})
    if label == "5xx":
        return httpx.Response(503, text="upstream is down")
    if label == "conn_error":
        return httpx.ConnectError("connection refused")
    if label == "timeout":
        return httpx.ReadTimeout("read timed out")
    raise AssertionError(f"unhandled outcome label: {label!r}")


def _expected_attempts(
    sequence: List[str], max_attempts: int = DEFAULT_MAX_ATTEMPTS
) -> Tuple[List[str], Optional[str]]:
    """Compute the labels that ``LangGraphClient.request`` should observe.

    The function walks the (cycled) ``sequence`` for up to
    ``max_attempts`` iterations, terminating early on the first
    terminal label.  Returns ``(observed_labels, terminal_or_None)``
    where ``terminal_or_None`` is the terminating label
    (``"2xx"``/``"4xx"``) or ``None`` when the retry budget is
    exhausted by retryable failures only.

    The oracle is intentionally written as an independent re-derivation
    of Property 9 (b)/(c) rather than a delegate to the SUT so a
    failing assertion really does mean the SUT and the design
    disagree.
    """

    observed: List[str] = []
    for i in range(max_attempts):
        label = sequence[i % len(sequence)]
        observed.append(label)
        if label in _TERMINAL_LABELS:
            return observed, label
    return observed, None


def _build_client(
    breaker: CircuitBreaker,
    *,
    retry_wait_multiplier: float = 0.0,
    retry_wait_min: float = 0.0,
    retry_wait_max: float = 0.0,
) -> LangGraphClient:
    """Build a :class:`LangGraphClient` with retry waits pinned by default.

    The defaults mirror the existing example-based tests in
    ``tests/clients/test_langgraph_client.py``: zero waits keep each
    Hypothesis example fast while still exercising
    :class:`tenacity.AsyncRetrying`'s wait/stop machinery.  The
    arguments are kept overridable so the dedicated delay test can
    swap in the design defaults.
    """

    return LangGraphClient(
        BASE_URL,
        breaker,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        retry_wait_multiplier=retry_wait_multiplier,
        retry_wait_min=retry_wait_min,
        retry_wait_max=retry_wait_max,
    )


def _cycle_side_effect(sequence: Iterable[str], target_length: int) -> list:
    """Materialise a ``respx`` ``side_effect`` list long enough to cover the budget.

    ``respx`` consumes ``side_effect`` lists via :func:`iter`, so we
    need the materialised list to be at least
    :data:`DEFAULT_MAX_ATTEMPTS` items long.  We deliberately do
    **not** use :func:`itertools.cycle` because ``respx`` snapshots the
    iterator on registration (see ``Route.snapshot``); a real cycle
    would expand to an unbounded list when snapshotted.
    """

    items = [_label_to_side_effect(label) for label in sequence]
    if not items:  # pragma: no cover — Hypothesis enforces min_size=1
        raise AssertionError("empty sequence is not allowed by the strategy")
    repeats = (target_length // len(items)) + 1
    return items * repeats


# ---------------------------------------------------------------------------
# Property 9 — main retry-policy property
# ---------------------------------------------------------------------------


@hypo_settings(
    max_examples=50,
    # Each example builds a fresh ``respx`` mock + ``httpx.AsyncClient``;
    # the per-example overhead can occasionally trip the default
    # ``too_slow`` and ``function_scoped_fixture`` health checks even
    # though the property body itself is sub-millisecond.
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
    ],
    deadline=None,
)
@given(
    sequence=st.lists(
        st.sampled_from(OUTCOME_LABELS),
        min_size=1,
        max_size=10,
    )
)
def test_retry_policy_property(sequence: List[str]) -> None:
    """**Validates: Requirements 14.3, 14.4, 14.5**

    For every drawn outcome ``sequence`` the SUT MUST:

    * issue ``len(observed_labels)`` upstream attempts (≤ 3),
    * never retry past a terminal label,
    * raise :class:`LangGraphUnavailable` iff every observed label is
      retryable and the budget is exhausted, and
    * surface a 2xx/4xx response verbatim otherwise.
    """

    observed_labels, terminal = _expected_attempts(
        sequence, DEFAULT_MAX_ATTEMPTS
    )
    expected_attempts = len(observed_labels)

    # Universal contract checks on the oracle itself — defending
    # against a future regression in ``_expected_attempts`` that
    # would let the property pass for the wrong reason.
    assert 1 <= expected_attempts <= DEFAULT_MAX_ATTEMPTS
    if terminal is None:
        # Retry budget exhausted -> every observed label must be
        # retryable.  Property 9 (c).
        assert all(label in _RETRYABLE_LABELS for label in observed_labels)
    else:
        # Property 9 (b): only the terminal label is non-retryable;
        # every prefix label must be retryable.
        assert terminal in _TERMINAL_LABELS
        assert all(
            label in _RETRYABLE_LABELS for label in observed_labels[:-1]
        )

    async def run() -> None:
        breaker = CircuitBreaker()
        client = _build_client(breaker)
        try:
            with respx.mock(
                base_url=BASE_URL,
                # Cycling can produce more side-effect items than
                # actual calls; ``assert_all_called`` (default ``True``)
                # only checks routes, not individual side-effect items,
                # so this stays consistent with respx semantics.
                assert_all_called=True,
            ) as router:
                cycled = _cycle_side_effect(
                    sequence, target_length=DEFAULT_MAX_ATTEMPTS
                )
                route = router.get("/threads").mock(side_effect=cycled)

                if terminal == "2xx":
                    response = await client.request("GET", "/threads")
                    assert response.status_code == 200, (
                        f"sequence={sequence!r} expected 200 on attempt "
                        f"{expected_attempts}, got {response.status_code}"
                    )
                elif terminal == "4xx":
                    response = await client.request("GET", "/threads")
                    assert response.status_code == 404, (
                        f"sequence={sequence!r} expected 404 on attempt "
                        f"{expected_attempts}, got {response.status_code}"
                    )
                else:
                    with pytest.raises(LangGraphUnavailable) as exc_info:
                        await client.request("GET", "/threads")
                    err = exc_info.value
                    # Property 9 (a): the budget MUST be exactly
                    # ``DEFAULT_MAX_ATTEMPTS`` when we exhaust on
                    # retryable failures.
                    assert expected_attempts == DEFAULT_MAX_ATTEMPTS
                    assert err.structured_error.code == "LANGGRAPH_UNAVAILABLE"

                # Property 9 (a): at most 3 attempts; ``call_count``
                # is the authoritative source because it counts
                # transport-level invocations, including the ones
                # that raised an exception.
                assert route.call_count == expected_attempts
                assert route.call_count <= DEFAULT_MAX_ATTEMPTS, (
                    f"sequence={sequence!r} produced {route.call_count} "
                    f"attempts, exceeding DEFAULT_MAX_ATTEMPTS="
                    f"{DEFAULT_MAX_ATTEMPTS}"
                )
        finally:
            await client.aclose()

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Breaker transition: ≥5 failures within 60s rolling window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breaker_transitions_to_open_after_five_failures_within_window() -> None:
    """**Validates: Requirements 14.4**

    Two back-to-back ``request`` calls against a perpetual 503 stub
    consume ``2 * DEFAULT_MAX_ATTEMPTS = 6`` attempts in well under
    60 seconds, so the rolling failure window MUST trip the breaker
    to ``Open`` before the second request finishes.
    """

    breaker = CircuitBreaker()  # default thresholds (5 / 60s / 30s / 2)
    assert breaker.failure_threshold == 5
    assert breaker.failure_window_seconds == 60.0

    client = _build_client(breaker)
    try:
        with respx.mock(base_url=BASE_URL) as router:
            router.get("/threads").mock(
                return_value=httpx.Response(503, text="boom")
            )

            assert breaker.state == BreakerState.CLOSED

            # First request consumes 3 attempts → 3 failures.  The
            # breaker is still closed because 3 < 5.
            with pytest.raises(LangGraphUnavailable):
                await client.request("GET", "/threads")
            assert breaker.state == BreakerState.CLOSED
            assert len(breaker.snapshot.failure_timestamps) == 3

            # Second request consumes up to 3 more attempts.  The 5th
            # failure trips the breaker to ``Open``; the 6th
            # short-circuits via :meth:`CircuitBreaker.allow_request`.
            with pytest.raises(LangGraphUnavailable):
                await client.request("GET", "/threads")

            assert breaker.state == BreakerState.OPEN, (
                "breaker did not transition to Open after 5 failures "
                "within the 60-second rolling window"
            )
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Delay-range assertion: every retry delay falls in [500ms, 4000ms]
# ---------------------------------------------------------------------------


def test_retry_delays_fall_within_500ms_4000ms_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Validates: Requirements 14.3**

    The design pins ``wait_exponential(multiplier=0.5, min=0.5,
    max=4.0)``.  We patch ``app.clients.langgraph.wait_exponential``
    with a recording wrapper that delegates to the real callable for
    the delay value but returns ``0`` to ``tenacity`` so the test
    runs in sub-second wall-clock time.  Every recorded delay must
    sit inside the closed range ``[DEFAULT_RETRY_WAIT_MIN,
    DEFAULT_RETRY_WAIT_MAX]``.
    """

    real_wait_exponential = langgraph_module.wait_exponential
    recorded: List[float] = []

    class _RecordingWaitExponential:
        """Drop-in replacement for :class:`tenacity.wait_exponential`."""

        def __init__(
            self,
            *,
            multiplier: float,
            min: float,  # noqa: A002 — match tenacity API
            max: float,  # noqa: A002 — match tenacity API
        ) -> None:
            # Sanity check: the SUT MUST construct ``wait_exponential``
            # with the design's documented parameters (R14.3).
            assert multiplier == DEFAULT_RETRY_WAIT_MULTIPLIER
            assert min == DEFAULT_RETRY_WAIT_MIN
            assert max == DEFAULT_RETRY_WAIT_MAX
            self._inner = real_wait_exponential(
                multiplier=multiplier, min=min, max=max
            )

        def __call__(self, retry_state) -> float:  # type: ignore[no-untyped-def]
            delay = float(self._inner(retry_state))
            recorded.append(delay)
            # Return 0 so ``tenacity`` does not actually sleep — the
            # property under test is the *value* tenacity computes,
            # not the wall-clock latency it imposes.
            return 0.0

    monkeypatch.setattr(
        langgraph_module, "wait_exponential", _RecordingWaitExponential
    )

    async def run() -> None:
        breaker = CircuitBreaker()
        client = _build_client(
            breaker,
            retry_wait_multiplier=DEFAULT_RETRY_WAIT_MULTIPLIER,
            retry_wait_min=DEFAULT_RETRY_WAIT_MIN,
            retry_wait_max=DEFAULT_RETRY_WAIT_MAX,
        )
        try:
            with respx.mock(base_url=BASE_URL) as router:
                router.get("/threads").mock(
                    return_value=httpx.Response(503, text="boom")
                )
                with pytest.raises(LangGraphUnavailable):
                    await client.request("GET", "/threads")
        finally:
            await client.aclose()

    asyncio.run(run())

    # Three attempts → at least two retries → at least two recorded
    # delays.  The exact count depends on tenacity's iter pipeline
    # (it computes ``upcoming_sleep`` once per iter), so we only
    # assert ``>=`` and constrain every observed value.
    assert len(recorded) >= DEFAULT_MAX_ATTEMPTS - 1, (
        f"expected at least {DEFAULT_MAX_ATTEMPTS - 1} recorded retry "
        f"delays, got {len(recorded)}"
    )
    for delay in recorded:
        assert DEFAULT_RETRY_WAIT_MIN <= delay <= DEFAULT_RETRY_WAIT_MAX, (
            f"recorded retry delay {delay} sits outside the design "
            f"range [{DEFAULT_RETRY_WAIT_MIN}, {DEFAULT_RETRY_WAIT_MAX}]"
        )
