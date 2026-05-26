"""Unit tests for ``app.clients.circuit_breaker`` (task 9.2).

These tests cover the four state transitions called out by Requirements
14.4 and 14.5:

* ``Closed -> Open`` after ≥5 failures inside the rolling 60-second
  window.
* ``Open -> HalfOpen`` after the 30-second probe interval has elapsed.
* ``HalfOpen -> Closed`` after 2 consecutive 2xx probes.
* ``HalfOpen -> Open`` on a single non-2xx probe.

Both the wall clock and :func:`asyncio.sleep` are stubbed so the tests
run in deterministic, sub-second time.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, List

import pytest

from app.clients.circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    CircuitBreakerState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeClock:
    """Manually advanced monotonic clock for deterministic tests."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = float(start)

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)

    def __call__(self) -> float:
        return self.now


def make_breaker(
    *,
    clock: FakeClock | None = None,
    failure_threshold: int = 5,
    failure_window_seconds: float = 60.0,
    probe_interval_seconds: float = 30.0,
    half_open_required_successes: int = 2,
) -> CircuitBreaker:
    """Return a :class:`CircuitBreaker` wired to a :class:`FakeClock`."""

    clock = clock or FakeClock()
    return CircuitBreaker(
        failure_threshold=failure_threshold,
        failure_window_seconds=failure_window_seconds,
        probe_interval_seconds=probe_interval_seconds,
        half_open_required_successes=half_open_required_successes,
        clock=clock,
    )


# ---------------------------------------------------------------------------
# Closed -> Open
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_starts_closed_and_allows_requests() -> None:
    breaker = make_breaker()
    assert breaker.state == BreakerState.CLOSED
    assert breaker.allow_request() is True
    assert isinstance(breaker.snapshot, CircuitBreakerState)


@pytest.mark.asyncio
async def test_four_failures_does_not_open_breaker() -> None:
    breaker = make_breaker()
    for _ in range(4):
        await breaker.on_failure()
    assert breaker.state == BreakerState.CLOSED
    assert breaker.allow_request() is True


@pytest.mark.asyncio
async def test_five_failures_in_window_opens_breaker() -> None:
    clock = FakeClock()
    breaker = make_breaker(clock=clock)

    for _ in range(5):
        await breaker.on_failure()

    assert breaker.state == BreakerState.OPEN
    assert breaker.allow_request() is False
    snap = breaker.snapshot
    assert snap.opened_at == pytest.approx(clock.now)
    assert len(snap.failure_timestamps) == 5


@pytest.mark.asyncio
async def test_failures_outside_window_are_trimmed() -> None:
    """Failures older than 60s must not contribute to the threshold."""

    clock = FakeClock()
    breaker = make_breaker(clock=clock)

    # Four failures at t=0..3.
    for _ in range(4):
        await breaker.on_failure()
        clock.advance(1.0)

    # Jump forward beyond the 60s window before the fifth failure.
    clock.advance(120.0)
    await breaker.on_failure()

    # The four early failures dropped out; only one entry survives, so
    # the breaker stays Closed.
    assert breaker.state == BreakerState.CLOSED
    assert len(breaker.snapshot.failure_timestamps) == 1


@pytest.mark.asyncio
async def test_on_success_in_closed_state_is_noop() -> None:
    breaker = make_breaker()
    # Three failures, still Closed.
    for _ in range(3):
        await breaker.on_failure()

    await breaker.on_success()

    # on_success must not silently drop the failure window.
    assert breaker.state == BreakerState.CLOSED
    assert len(breaker.snapshot.failure_timestamps) == 3


# ---------------------------------------------------------------------------
# Open -> HalfOpen via probe_loop
# ---------------------------------------------------------------------------


def _drive_breaker_open(breaker: CircuitBreaker) -> Awaitable[None]:
    """Push the breaker straight into ``Open`` for a probe-loop test."""

    async def _impl() -> None:
        for _ in range(breaker.failure_threshold):
            await breaker.on_failure()

    return _impl()


@pytest.mark.asyncio
async def test_open_to_halfopen_after_probe_interval() -> None:
    """One sleep tick + a 2xx probe must transition Open -> HalfOpen.

    With ``half_open_required_successes=2`` (default), a single 2xx
    probe leaves the breaker in ``HalfOpen``.  The follow-up
    transition to ``Closed`` is exercised by
    :func:`test_halfopen_to_closed_after_two_successes`.
    """

    clock = FakeClock()
    breaker = make_breaker(clock=clock)
    await _drive_breaker_open(breaker)
    assert breaker.state == BreakerState.OPEN

    sleep_calls: List[float] = []
    iterations = {"count": 0}

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)
        iterations["count"] += 1
        if iterations["count"] >= 1:
            # Allow the probe to run, then cancel the loop on the next
            # sleep to keep the test deterministic.
            await asyncio.sleep(0)
            return
        await asyncio.sleep(0)

    async def probe_fn() -> int:
        return 200

    task = asyncio.create_task(
        breaker.probe_loop(probe_fn, sleep=fake_sleep, clock=clock)
    )

    # Yield enough times for one sleep + one probe + one more sleep.
    for _ in range(10):
        await asyncio.sleep(0)
        if breaker.state == BreakerState.HALF_OPEN:
            break

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert sleep_calls and sleep_calls[0] == pytest.approx(30.0)
    assert breaker.state == BreakerState.HALF_OPEN
    assert breaker.snapshot.success_count == 1


# ---------------------------------------------------------------------------
# HalfOpen -> Closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_halfopen_to_closed_after_two_successes() -> None:
    clock = FakeClock()
    breaker = make_breaker(clock=clock)
    await _drive_breaker_open(breaker)

    probe_results = [200, 200, 200]
    probe_index = {"i": 0}

    async def fake_sleep(duration: float) -> None:
        await asyncio.sleep(0)

    async def probe_fn() -> int:
        i = probe_index["i"]
        probe_index["i"] = i + 1
        return probe_results[min(i, len(probe_results) - 1)]

    task = asyncio.create_task(
        breaker.probe_loop(probe_fn, sleep=fake_sleep, clock=clock)
    )

    for _ in range(50):
        await asyncio.sleep(0)
        if breaker.state == BreakerState.CLOSED:
            break

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert breaker.state == BreakerState.CLOSED
    # Failure window is cleared on close.
    assert len(breaker.snapshot.failure_timestamps) == 0
    assert breaker.snapshot.success_count == 0
    assert breaker.snapshot.opened_at is None
    # At least two probes were issued before the breaker closed.
    assert probe_index["i"] >= 2


@pytest.mark.asyncio
async def test_halfopen_one_success_remains_halfopen() -> None:
    """A single 2xx probe in HalfOpen does not close the breaker."""

    breaker = make_breaker(half_open_required_successes=2)
    await _drive_breaker_open(breaker)

    # Drive Open -> HalfOpen manually using the internal helper, then
    # record one success.
    await breaker._enter_half_open()  # noqa: SLF001
    assert breaker.state == BreakerState.HALF_OPEN

    await breaker.on_success()

    assert breaker.state == BreakerState.HALF_OPEN
    assert breaker.snapshot.success_count == 1


# ---------------------------------------------------------------------------
# HalfOpen -> Open
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_halfopen_to_open_on_non_2xx_probe() -> None:
    breaker = make_breaker()
    await _drive_breaker_open(breaker)
    await breaker._enter_half_open()  # noqa: SLF001
    assert breaker.state == BreakerState.HALF_OPEN

    await breaker.on_failure()

    assert breaker.state == BreakerState.OPEN
    assert breaker.snapshot.success_count == 0


@pytest.mark.asyncio
async def test_probe_loop_failure_resets_to_open() -> None:
    """An end-to-end probe_loop run with a 5xx probe must re-open."""

    clock = FakeClock()
    breaker = make_breaker(clock=clock)
    await _drive_breaker_open(breaker)
    await breaker._enter_half_open()  # noqa: SLF001
    # Bank one success so the test exercises the reset path.
    await breaker.on_success()
    assert breaker.snapshot.success_count == 1

    async def fake_sleep(duration: float) -> None:
        await asyncio.sleep(0)

    async def probe_fn() -> int:
        return 502

    task = asyncio.create_task(
        breaker.probe_loop(probe_fn, sleep=fake_sleep, clock=clock)
    )

    for _ in range(20):
        await asyncio.sleep(0)
        if breaker.state == BreakerState.OPEN and breaker.snapshot.success_count == 0:
            break

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert breaker.state == BreakerState.OPEN
    assert breaker.snapshot.success_count == 0
    assert breaker.allow_request() is False


# ---------------------------------------------------------------------------
# allow_request gating + probe loop cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allow_request_truth_table() -> None:
    breaker = make_breaker()
    assert breaker.allow_request() is True  # Closed

    await _drive_breaker_open(breaker)
    assert breaker.allow_request() is False  # Open

    await breaker._enter_half_open()  # noqa: SLF001
    assert breaker.allow_request() is True  # HalfOpen


@pytest.mark.asyncio
async def test_probe_loop_cancellation_propagates_cleanly() -> None:
    breaker = make_breaker()

    sleeps: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleeps.append(duration)
        await asyncio.sleep(0)

    async def probe_fn() -> int:
        return 200

    task = asyncio.create_task(breaker.probe_loop(probe_fn, sleep=fake_sleep))
    # Let the loop run a few iterations.
    for _ in range(3):
        await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert task.done()


@pytest.mark.asyncio
async def test_probe_loop_swallows_probe_exceptions() -> None:
    """A raising probe_fn must be treated as a failure, not crash the loop."""

    clock = FakeClock()
    breaker = make_breaker(clock=clock)
    await _drive_breaker_open(breaker)

    async def fake_sleep(duration: float) -> None:
        await asyncio.sleep(0)

    calls = {"n": 0}

    async def probe_fn() -> int:
        calls["n"] += 1
        raise RuntimeError("boom")

    task = asyncio.create_task(
        breaker.probe_loop(probe_fn, sleep=fake_sleep, clock=clock)
    )

    for _ in range(10):
        await asyncio.sleep(0)
        if calls["n"] >= 2:
            break

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Loop kept running and logged failures rather than crashing.
    assert calls["n"] >= 1
    assert breaker.state == BreakerState.OPEN


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"failure_threshold": 0},
        {"failure_window_seconds": 0},
        {"probe_interval_seconds": -1},
        {"half_open_required_successes": 0},
    ],
)
def test_constructor_rejects_invalid_arguments(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        CircuitBreaker(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Probe result handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bool_probe_results_are_supported() -> None:
    """``probe_fn`` returning ``True``/``False`` must work alongside ints."""

    clock = FakeClock()
    breaker = make_breaker(clock=clock)
    await _drive_breaker_open(breaker)
    await breaker._enter_half_open()  # noqa: SLF001

    async def fake_sleep(duration: float) -> None:
        await asyncio.sleep(0)

    sequence = iter([True, True])

    async def probe_fn() -> bool:
        return next(sequence)

    task = asyncio.create_task(
        breaker.probe_loop(probe_fn, sleep=fake_sleep, clock=clock)
    )

    for _ in range(20):
        await asyncio.sleep(0)
        if breaker.state == BreakerState.CLOSED:
            break

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert breaker.state == BreakerState.CLOSED
