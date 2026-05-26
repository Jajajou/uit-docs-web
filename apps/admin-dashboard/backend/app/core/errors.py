"""Structured error envelope (design D1).

The :class:`Structured_Error` Pydantic model is the single shape used by
``Admin_Backend`` and by ``scripts/smoke_test.sh`` to surface failures.
The ``code`` field is **closed** — the allowed values are enumerated in
design D1 and additions require a design-review change.

The model is exposed under both ``Structured_Error`` (matching the name
used throughout the spec/design) and ``StructuredError`` (PEP 8) so call
sites are free to use whichever style fits their context.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Closed code set (design D1).
#
# The codes below are the *baseline* enumerated in design D1 plus the smoke
# script codes referenced in design section E5.  Adding a new code requires a
# design-review change because the value is part of the public contract.
# ---------------------------------------------------------------------------

StructuredErrorCode = Literal[
    # --- D1 baseline -------------------------------------------------------
    "LANGGRAPH_UNAVAILABLE",
    "LANGGRAPH_UPSTREAM_URL_MISSING",
    "CORS_MISCONFIGURED",
    "TRUSTED_HOSTS_MISCONFIGURED",
    "BAD_ARG",
    "SMOKE_TIMEOUT",
    "SMOKE_HTTP_FAIL",
    # --- Smoke-test extension (design E5, used by task 8.1) ---------------
    "SMOKE_DNS_ERROR",
    "SMOKE_TLS_ERROR",
    "SMOKE_BUDGET_EXCEEDED",
]


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601, second-precision string."""

    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_request_id() -> str:
    """Generate a fresh UUIDv4 string for the ``request_id`` field."""

    return str(uuid.uuid4())


class StructuredError(BaseModel):
    """Single error envelope (design D1).

    All fields are required.  ``code`` is constrained to the closed set
    declared in :data:`StructuredErrorCode` and validated by Pydantic at
    construction time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: StructuredErrorCode = Field(
        ...,
        description=(
            "Stable machine identifier from the closed set defined in "
            "design D1."
        ),
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Human-readable message; never contains secret values.",
    )
    request_id: str = Field(
        default_factory=_new_request_id,
        description=(
            "Non-empty UUID/ULID, taken from ``X-Request-Id`` when "
            "available or freshly generated."
        ),
    )
    timestamp: str = Field(
        default_factory=_utc_now_iso,
        description="UTC ISO 8601, second precision.",
    )

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("message must be a non-empty string")
        return value

    @field_validator("request_id")
    @classmethod
    def _request_id_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("request_id must be a non-empty string")
        return value

    @field_validator("timestamp")
    @classmethod
    def _timestamp_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("timestamp must be a non-empty string")
        return value


# Public alias matching the design/spec spelling.  Callers may prefer
# ``Structured_Error`` to mirror the design document literally.
Structured_Error = StructuredError

__all__ = [
    "StructuredError",
    "StructuredErrorCode",
    "Structured_Error",
]
