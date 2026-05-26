"""Circuit breaker for the LangGraph upstream client (design C10).

This module implements the state machine documented in design section
C10 and codified by Requirements 14.4 and 14.5:

* The breaker maintains a **rolling 60-second window** of failure
  timestamps.  When the window count reaches the failure threshold
  (default ``5``), the breaker transitions ``Closed -> Open``.
* While ``Open``, every new request is short-circuited at the client
  level (``allow_request()`` returns ``False``); the LangGraph client
  surfaces this as HTTP 503 with ``Structured_Error``
  ``code="LANGGRAPH_UNAVAILABLE"``.
* A background coroutine (:meth:`CircuitBreaker.probe_loop`) wakes up
  every ``probe_interval`` seconds (default ``30``).  When the breaker
  is ``Open`` it transitions to ``HalfOpen`` and issues exactly one
  probe via the caller-supplied probe callable.
* In ``HalfOpen`` a 2xx probe increments ``success_count``; reaching
  ``half_open_required_successes`` (default ``2``) closes the breaker
  and clears the failure window.  Any non-2xx probe in ``HalfOpen``
  immediately re-opens the breaker and resets ``success_count``.

The module is intentionally framework-free — it does **not** import
``httpx``, ``fastapi``, or any other transport library.  The probe
callable is supplied by the LangGraph client (task 9.3) and the
``probe_loop`` coroutine is spawned by the FastAPI ``lifespan`` hook
(task 9.4).  This keeps the breaker easy to unit-test with injected
clocks and probe functions.

The default :data:`StateName` literal values match the design table
verbatim so logs and tests can reuse them without translation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases and defaults
# ---------------------------------------------------------------------------

#: Allowed state names; these literals match design C10 verbatim.
StateName = Literal["Closed", "Open", "HalfOpen"]

#: Probe-callable return type.  Implementations may return either a bool
#: (``True`` for "treat as 2xx") or an integer HTTP status code.  This
#: keeps the breaker decoupled from any specific HTTP library.
ProbeResult = bool | int

#: Async probe callable signature.
ProbeCallable = Callable[[], Awaitable[ProbeResult]]

#: Clock callable returning a monotonic timestamp in seconds.
ClockCallable = Callable[[], float]

#: Async sleep callable; matches :func:`asyncio.sleep`.
SleepCallable = Callable[[float], Awaitable[None]]

#: Default failure threshold (Requirement 14.4 — "≥5 failures in 60s").
DEFAULT_FAILURE_THRESHOLD: Final[int] = 5

#: Default failure window in seconds (Requirement 14.4).
DEFAULT_FAILURE_WINDOW_SECONDS: Final[float] = 60.0

#: Default probe interval in seconds (Requirement 14.5).
DEFAULT_PROBE_INTERVAL_SECONDS: Final[float] = 30.0

#: Default number of consecutive 2xx probes required to close the
#: breaker from ``HalfOpen`` (Requirement 14.5).
DEFAULT_HALF_OPEN_REQUIRED_SUCCESSES: Final[int] = 2


#: Synchronous listener invoked on every state transition (task 10.5).
#: Receives the *new* state name as its single argument.  Listeners
#: are fired from inside the breaker lock, so they must complete
#: quickly and must not call back into the breaker (which would
#: deadlock).  The Prometheus metrics module installs a listener that
#: writes the numeric encoding of the new state into a
#: :class:`~prometheus_client.Gauge` so design C13's
#: ``langgraph_circuit_state`` gauge is updated synchronously on every
#: transition (R17.6).
StateListener = Callable[[StateName], None]


# ---------------------------------------------------------------------------
# State enum (kept as a small helper for callers that prefer constants)
# ---------------------------------------------------------------------------


class BreakerState:
    """String constants for the three breaker states (design C10).

    The class is intentionally a namespace rather than an
    :class:`enum.Enum` so the values stay JSON-serialisable and round
    trip cleanly through structured log emitters and Prometheus labels.
    """

    CLOSED: Final[StateName] = "Closed"
    OPEN: Final[StateName] = "Open"
    HALF_OPEN: Final[StateName] = "HalfOpen"

    ALL: Final[tuple[StateName, ...]] = ("Closed", "Open", "HalfOpen")


# ---------------------------------------------------------------------------
# Dataclass holding mutable breaker state
# ---------------------------------------------------------------------------


@dataclass
class CircuitBreakerState:
    """Mutable state for a :class:`CircuitBreaker` instance.

    The dataclass is exposed so tests and observability code can read
    the current values without going through the breaker's public API
    (which is async-locked and therefore awkward to call from
    synchronous test setup).

    Attributes:
        name: One of ``"Closed"``, ``"Open"``, ``"HalfOpen"``.
        failure_timestamps: Monotonic timestamps of failures inside the
            rolling failure window.  Older entries are trimmed by
            :meth:`CircuitBreaker.on_failure` on every append.
        opened_at: Monotonic timestamp at which the breaker last
            transitioned to ``Open``.  ``None`` when the breaker has
            never opened or is currently ``Closed``.
        success_count: Number of consecutive successful probes observed
            while in ``HalfOpen``.  Reset to ``0`` on any non-2xx probe
            and on every transition into ``Open``.
    """

    name: StateName = BreakerState.CLOSED
    failure_timestamps: deque[float] = field(default_factory=deque)
    opened_at: float | None = None
    success_count: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_success(result: ProbeResult) -> bool:
    """Return ``True`` iff a probe result represents an HTTP 2xx outcome.

    Booleans are mapped directly (``True`` -> success).  Integers are
    treated as HTTP status codes — only the ``[200, 300)`` range counts
    as success, matching design C10 ("any non-2xx probe in HalfOpen ->
    Open").
    """

    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return 200 <= result < 300
    # Any other type is treated as a failure — the probe contract is
    # documented as ``bool | int``.
    return False


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Rolling 60-second failure-window circuit breaker (design C10).

    The breaker is **transport-agnostic**: callers tell it about
    successes and failures via :meth:`on_success` / :meth:`on_failure`
    and ask for permission via :meth:`allow_request`.  The breaker has
    no knowledge of HTTP, ``httpx``, or FastAPI.

    Args:
        failure_threshold: Minimum number of failures in the rolling
            window required to trip the breaker (default ``5``).
        failure_window_seconds: Length of the rolling failure window in
            seconds (default ``60.0``).
        probe_interval_seconds: How often :meth:`probe_loop` issues a
            probe while ``Open`` or ``HalfOpen`` (default ``30.0``).
        half_open_required_successes: Number of consecutive 2xx probes
            required to transition ``HalfOpen -> Closed`` (default
            ``2``).
        clock: Callable returning a monotonic timestamp in seconds.
            Injectable for tests; defaults to :func:`time.monotonic`.

    The breaker is safe to share across coroutines — every public
    state-mutating call is serialised through an internal
    :class:`asyncio.Lock`.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        failure_window_seconds: float = DEFAULT_FAILURE_WINDOW_SECONDS,
        probe_interval_seconds: float = DEFAULT_PROBE_INTERVAL_SECONDS,
        half_open_required_successes: int = DEFAULT_HALF_OPEN_REQUIRED_SUCCESSES,
        clock: ClockCallable = time.monotonic,
        state_listeners: list[StateListener] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if failure_window_seconds <= 0:
            raise ValueError("failure_window_seconds must be > 0")
        if probe_interval_seconds <= 0:
            raise ValueError("probe_interval_seconds must be > 0")
        if half_open_required_successes < 1:
            raise ValueError("half_open_required_successes must be >= 1")

        self._failure_threshold = failure_threshold
        self._failure_window_seconds = failure_window_seconds
        self._probe_interval_seconds = probe_interval_seconds
        self._half_open_required_successes = half_open_required_successes
        self._clock = clock

        # Synchronous state-transition listeners.  Task 10.5 uses this
        # hook to update the ``langgraph_circuit_state`` Prometheus
        # gauge in lock-step with the breaker.  The list itself is
        # exposed publicly so callers can append/remove listeners
        # after construction without resorting to a private attribute.
        self.state_listeners: list[StateListener] = (
            list(state_listeners) if state_listeners else []
        )

        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public read-only accessors
    # ------------------------------------------------------------------

    @property
    def state(self) -> StateName:
        """Return the current state name (``"Closed"``/``"Open"``/``"HalfOpen"``)."""

        return self._state.name

    @property
    def snapshot(self) -> CircuitBreakerState:
        """Return the underlying :class:`CircuitBreakerState` dataclass.

        The returned object is the live instance — callers must not
        mutate it directly.  It is exposed so observability code (the
        Prometheus gauge, ``/healthz`` handler) can read fields cheaply
        without acquiring the lock.
        """

        return self._state

    @property
    def failure_threshold(self) -> int:
        """Configured failure threshold."""

        return self._failure_threshold

    @property
    def failure_window_seconds(self) -> float:
        """Configured rolling failure-window length, in seconds."""

        return self._failure_window_seconds

    @property
    def probe_interval_seconds(self) -> float:
        """Configured probe interval, in seconds."""

        return self._probe_interval_seconds

    @property
    def half_open_required_successes(self) -> int:
        """Configured number of consecutive 2xx probes to close the breaker."""

        return self._half_open_required_successes

    # ------------------------------------------------------------------
    # Request gating
    # ------------------------------------------------------------------

    def allow_request(self) -> bool:
        """Return ``True`` iff a new upstream request may be issued.

        Per Requirement 14.4 + 14.7, requests are short-circuited only
        in the ``Open`` state.  ``HalfOpen`` allows requests through
        (the LangGraph client treats success/failure of those requests
        as breaker probes via :meth:`on_success` / :meth:`on_failure`).
        ``Closed`` always allows requests.
        """

        return self._state.name != BreakerState.OPEN

    # ------------------------------------------------------------------
    # State transitions driven by request outcomes
    # ------------------------------------------------------------------

    async def on_success(self) -> None:
        """Record a successful upstream interaction.

        Behaviour by current state:

        * ``Closed``: no-op (failure window is preserved as-is so that
          a stale failure cluster cannot be silently masked by a single
          recent success).
        * ``HalfOpen``: increments ``success_count``; once it reaches
          ``half_open_required_successes`` the breaker transitions to
          ``Closed`` and the failure window is cleared.
        * ``Open``: defensive guard — successes received while ``Open``
          are treated as a probe success and routed through the
          ``HalfOpen`` increment path.  This keeps the breaker robust
          against callers that race against a state transition.
        """

        async with self._lock:
            if self._state.name == BreakerState.CLOSED:
                return
            if self._state.name == BreakerState.OPEN:
                # Treat as if we just transitioned through HalfOpen.
                self._state.name = BreakerState.HALF_OPEN
                self._state.success_count = 0
            self._state.success_count += 1
            if self._state.success_count >= self._half_open_required_successes:
                self._transition_to_closed_locked()

    async def on_failure(self) -> None:
        """Record a failed upstream interaction.

        Behaviour by current state:

        * ``Closed``: appends the current monotonic timestamp to the
          rolling window, trims entries older than
          ``failure_window_seconds``, and transitions to ``Open`` if
          the window count reaches ``failure_threshold``.
        * ``HalfOpen``: immediately transitions back to ``Open`` and
          resets ``success_count`` to ``0`` (Requirement 14.5 — "any
          non-2xx probe in HalfOpen -> Open").
        * ``Open``: no-op other than refreshing the failure window so
          that the breaker stays open while failures persist.
        """

        async with self._lock:
            now = self._clock()
            self._record_failure_locked(now)

            if self._state.name == BreakerState.HALF_OPEN:
                self._transition_to_open_locked(now)
                return

            if (
                self._state.name == BreakerState.CLOSED
                and len(self._state.failure_timestamps) >= self._failure_threshold
            ):
                self._transition_to_open_locked(now)

    # ------------------------------------------------------------------
    # Probe loop
    # ------------------------------------------------------------------

    async def probe_loop(
        self,
        probe_fn: ProbeCallable,
        *,
        sleep: SleepCallable = asyncio.sleep,
        clock: ClockCallable | None = None,
    ) -> None:
        """Run the periodic probe loop forever (until cancelled).

        The loop is intended to be spawned as an :class:`asyncio.Task`
        from the FastAPI ``lifespan`` startup hook (task 9.4) and
        cancelled cleanly on shutdown.  The coroutine performs the
        following actions in a loop:

        1. ``await sleep(probe_interval_seconds)``.
        2. If the breaker is ``Closed``, do nothing — failures will
           re-open the breaker on demand.
        3. If the breaker is ``Open``, transition to ``HalfOpen`` and
           call ``probe_fn`` exactly once.  A 2xx result calls
           :meth:`on_success`; any other result calls
           :meth:`on_failure` (which re-opens the breaker).
        4. If the breaker is already ``HalfOpen`` (because the previous
           tick transitioned it there but we're still gathering the
           required successes), call ``probe_fn`` again.

        Args:
            probe_fn: Async callable returning a :class:`ProbeResult`.
                Typically wraps an HTTP GET on the upstream's
                ``/health`` endpoint.
            sleep: Async sleep function; injectable for tests.
            clock: Optional clock override; falls back to the
                breaker's own clock.

        Cancellation: the coroutine catches
        :class:`asyncio.CancelledError` so the cancellation propagates
        cleanly to the caller without leaking partial state.
        Exceptions raised by ``probe_fn`` are caught and recorded as
        failures so a misbehaving probe cannot crash the loop.
        """

        active_clock = clock if clock is not None else self._clock
        try:
            while True:
                try:
                    await sleep(self._probe_interval_seconds)
                except asyncio.CancelledError:
                    raise

                if self._state.name == BreakerState.CLOSED:
                    # Nothing to do — the breaker only probes while
                    # Open or HalfOpen.
                    continue

                if self._state.name == BreakerState.OPEN:
                    await self._enter_half_open()

                # Issue exactly one probe per tick.  Any exception is
                # treated as a failure to keep the loop alive.
                try:
                    started = active_clock()
                    result = await probe_fn()
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 — all exceptions = failure
                    logger.warning(
                        "circuit_breaker.probe_failed",
                        extra={"state": self._state.name},
                        exc_info=True,
                    )
                    await self.on_failure()
                    continue

                # ``started`` is captured for symmetry / future logging
                # — the value is intentionally not used yet.
                _ = started

                if _is_success(result):
                    await self.on_success()
                else:
                    await self.on_failure()
        except asyncio.CancelledError:
            logger.debug("circuit_breaker.probe_loop.cancelled")
            raise

    # ------------------------------------------------------------------
    # Internal helpers (lock must already be held by caller)
    # ------------------------------------------------------------------

    def _record_failure_locked(self, now: float) -> None:
        """Append ``now`` to the failure window and trim old entries."""

        window = self._state.failure_timestamps
        window.append(now)
        cutoff = now - self._failure_window_seconds
        while window and window[0] < cutoff:
            window.popleft()

    def _transition_to_open_locked(self, now: float) -> None:
        """Transition to ``Open`` and reset ``success_count``."""

        already_open = self._state.name == BreakerState.OPEN
        if not already_open:
            logger.info(
                "circuit_breaker.transition",
                extra={"from": self._state.name, "to": BreakerState.OPEN},
            )
        self._state.name = BreakerState.OPEN
        self._state.opened_at = now
        self._state.success_count = 0
        if not already_open:
            self._notify_state_change_locked(BreakerState.OPEN)

    def _transition_to_closed_locked(self) -> None:
        """Transition to ``Closed`` and clear the failure window."""

        already_closed = self._state.name == BreakerState.CLOSED
        if not already_closed:
            logger.info(
                "circuit_breaker.transition",
                extra={"from": self._state.name, "to": BreakerState.CLOSED},
            )
        self._state.name = BreakerState.CLOSED
        self._state.failure_timestamps.clear()
        self._state.opened_at = None
        self._state.success_count = 0
        if not already_closed:
            self._notify_state_change_locked(BreakerState.CLOSED)

    async def _enter_half_open(self) -> None:
        """Transition ``Open -> HalfOpen`` (probe-loop helper)."""

        async with self._lock:
            if self._state.name != BreakerState.OPEN:
                return
            logger.info(
                "circuit_breaker.transition",
                extra={"from": BreakerState.OPEN, "to": BreakerState.HALF_OPEN},
            )
            self._state.name = BreakerState.HALF_OPEN
            self._state.success_count = 0
            self._notify_state_change_locked(BreakerState.HALF_OPEN)

    def _notify_state_change_locked(self, new_state: StateName) -> None:
        """Fire every state listener synchronously.

        Called from inside the breaker lock so listeners observe state
        transitions in the exact order they happen and so the
        ``langgraph_circuit_state`` gauge in design C13 cannot lag the
        breaker (R17.6).  A listener that raises is logged but does
        not abort the transition — observability hooks must never
        prevent the breaker from changing state.
        """

        for listener in self.state_listeners:
            try:
                listener(new_state)
            except Exception:  # noqa: BLE001 — listeners must not break the breaker
                logger.warning(
                    "circuit_breaker.state_listener_failed",
                    extra={"new_state": new_state},
                    exc_info=True,
                )


__all__ = [
    "BreakerState",
    "CircuitBreaker",
    "CircuitBreakerState",
    "ClockCallable",
    "ProbeCallable",
    "ProbeResult",
    "SleepCallable",
    "StateListener",
    "StateName",
]
