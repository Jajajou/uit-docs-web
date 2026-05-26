"""Prometheus metrics endpoint (task 10.5, R17.6, design C13).

This module wires the Prometheus observability surface into the FastAPI
app:

* HTTP request volume and latency are produced by
  ``prometheus-fastapi-instrumentator``'s default instrumentation, which
  emits ``http_requests_total{method,status,handler}`` and
  ``http_request_duration_seconds{method,handler}`` (design C13's first
  two metrics).
* A custom ``langgraph_upstream_failures_total{kind}`` counter is
  registered for the LangGraph client to increment on every retryable
  failure (kinds ``timeout``, ``conn_error``, ``http_5xx``).
* A custom ``langgraph_circuit_state`` gauge encodes the breaker state
  per design C13 (``Closed=0``, ``HalfOpen=1``, ``Open=2``) and is
  updated **synchronously** on every breaker transition through a
  listener that the breaker fires from inside its lock.

Each :func:`setup_metrics` call uses its own
:class:`prometheus_client.CollectorRegistry` so multiple FastAPI apps
constructed in the same process (e.g. across tests) do not collide on
the global default registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from app.clients.circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    StateName,
)

# ---------------------------------------------------------------------------
# Constants — keep aligned with design C13 and the LangGraph client
# ---------------------------------------------------------------------------

#: Allowed failure-kind labels for ``langgraph_upstream_failures_total``
#: (design C13).  The LangGraph client increments the counter using one
#: of these literals.
FAILURE_KIND_TIMEOUT: Final[str] = "timeout"
FAILURE_KIND_CONN_ERROR: Final[str] = "conn_error"
FAILURE_KIND_HTTP_5XX: Final[str] = "http_5xx"

ALLOWED_FAILURE_KINDS: Final[frozenset[str]] = frozenset(
    {FAILURE_KIND_TIMEOUT, FAILURE_KIND_CONN_ERROR, FAILURE_KIND_HTTP_5XX}
)

#: Numeric encoding of breaker states for the ``langgraph_circuit_state``
#: gauge (design C13).  These literal values are part of the contract —
#: Grafana dashboards and alert rules read them directly and must not
#: change.
CIRCUIT_STATE_VALUES: Final[dict[StateName, float]] = {
    BreakerState.CLOSED: 0.0,
    BreakerState.HALF_OPEN: 1.0,
    BreakerState.OPEN: 2.0,
}

#: Endpoint at which the metrics are exposed.  Must stay at ``/metrics``
#: per design C13 so the Prometheus scrape target stays stable.
METRICS_ENDPOINT: Final[str] = "/metrics"


# ---------------------------------------------------------------------------
# Public bundle returned by ``setup_metrics``
# ---------------------------------------------------------------------------


@dataclass
class MetricsHandles:
    """Bundle returned by :func:`setup_metrics` for caller-side use.

    Holding the handles on ``app.state.metrics`` lets request handlers
    and the LangGraph client increment counters without re-discovering
    them through the registry.

    Attributes:
        registry: Per-app :class:`prometheus_client.CollectorRegistry`
            that owns every metric produced by ``Admin_Backend``.
        upstream_failures_total: Counter incremented by the LangGraph
            client on every retryable failure.  Labelled by ``kind``.
        circuit_state: Gauge updated synchronously on every breaker
            transition.  ``0=Closed``, ``1=HalfOpen``, ``2=Open``.
        instrumentator: The configured instrumentator (kept so tests
            can introspect or further customise it).
    """

    registry: CollectorRegistry
    upstream_failures_total: Counter
    circuit_state: Gauge
    instrumentator: Instrumentator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_to_gauge_value(state: StateName) -> float:
    """Map a breaker state name to the gauge value defined by design C13."""

    try:
        return CIRCUIT_STATE_VALUES[state]
    except KeyError as exc:  # pragma: no cover — guarded by StateName literals
        raise ValueError(f"unknown circuit-breaker state: {state!r}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_metrics(app: FastAPI, breaker: CircuitBreaker) -> MetricsHandles:
    """Install Prometheus metrics on ``app`` and bind them to ``breaker``.

    The function is intended to be called exactly once per app, from
    :func:`app.main.create_app` after the production-hardening
    middlewares are in place.  Tests build a fresh app per case so each
    invocation gets its own :class:`CollectorRegistry`.

    Args:
        app: FastAPI app to instrument.  ``/metrics`` is added to its
            router and the instrumentator middleware is added to its
            stack (which means the app must not have started yet —
            Starlette locks the middleware stack on first request).
        breaker: Circuit breaker whose state drives the
            ``langgraph_circuit_state`` gauge.  ``setup_metrics``
            appends a synchronous listener to
            :pyattr:`CircuitBreaker.state_listeners` so the gauge is
            updated in lock-step with every transition (design C13).

    Returns:
        A :class:`MetricsHandles` bundle that is also attached to
        ``app.state.metrics`` for downstream code (e.g. the LangGraph
        client) to discover the counters it should increment.
    """

    # Per-app registry: keeps tests isolated, avoids ``Duplicated
    # timeseries`` errors when multiple FastAPI apps are constructed in
    # the same Python process, and makes the ``/metrics`` payload
    # exactly mirror what *this* app produced.
    registry = CollectorRegistry()

    upstream_failures_total = Counter(
        "langgraph_upstream_failures_total",
        "Total LangGraph upstream failures broken down by kind.",
        labelnames=("kind",),
        registry=registry,
    )
    # Pre-register the three allowed label values so the metric is
    # exposed with a 0-valued series even before the first failure
    # happens.  Design C13 enumerates the kinds explicitly so
    # dashboards expecting them don't break on a freshly started
    # backend.
    for kind in sorted(ALLOWED_FAILURE_KINDS):
        upstream_failures_total.labels(kind=kind)

    circuit_state = Gauge(
        "langgraph_circuit_state",
        "Circuit-breaker state: 0=Closed, 1=HalfOpen, 2=Open.",
        registry=registry,
    )
    # Initialise the gauge from the breaker's current state so the
    # first scrape (before any transition fires) reports the truth
    # rather than the prometheus_client default of 0.
    circuit_state.set(_state_to_gauge_value(breaker.state))

    def _on_state_change(new_state: StateName) -> None:
        """Synchronous breaker listener — updates the gauge in-place.

        Runs inside the breaker lock (see
        :meth:`CircuitBreaker._notify_state_change_locked`), so the
        gauge is guaranteed to reflect the latest transition before any
        other coroutine can observe a different breaker state.
        """

        circuit_state.set(_state_to_gauge_value(new_state))

    breaker.state_listeners.append(_on_state_change)

    # ``Instrumentator`` registers ``http_requests_total`` and
    # ``http_request_duration_seconds`` (alongside a few auxiliary
    # metrics) into ``registry`` via its default instrumentation.  The
    # ``expose`` call adds ``GET /metrics`` to the FastAPI router and
    # serves the registry's text exposition format.
    instrumentator = Instrumentator(registry=registry)
    instrumentator.instrument(app).expose(
        app,
        endpoint=METRICS_ENDPOINT,
        include_in_schema=False,
    )

    handles = MetricsHandles(
        registry=registry,
        upstream_failures_total=upstream_failures_total,
        circuit_state=circuit_state,
        instrumentator=instrumentator,
    )
    app.state.metrics = handles
    return handles


__all__ = [
    "ALLOWED_FAILURE_KINDS",
    "CIRCUIT_STATE_VALUES",
    "FAILURE_KIND_CONN_ERROR",
    "FAILURE_KIND_HTTP_5XX",
    "FAILURE_KIND_TIMEOUT",
    "METRICS_ENDPOINT",
    "MetricsHandles",
    "setup_metrics",
]
