"""HTTP clients used by ``Admin_Backend``.

This package currently hosts the LangGraph upstream contract surface:

* :mod:`circuit_breaker` — rolling 60-second failure-window state
  machine that protects ``Admin_Backend`` from a degraded LangGraph
  upstream (design C10, R14.4, R14.5).
* :mod:`langgraph` — defensive HTTP client wired to the breaker, with
  the design's tenacity retry policy and structured-error envelope
  on retry exhaustion (design C10, R14.2, R14.3, R14.6, R14.9).
"""

from .circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    CircuitBreakerState,
)
from .langgraph import (
    LangGraphClient,
    LangGraphUnavailable,
    redact_url,
)

__all__ = [
    "BreakerState",
    "CircuitBreaker",
    "CircuitBreakerState",
    "LangGraphClient",
    "LangGraphUnavailable",
    "redact_url",
]
