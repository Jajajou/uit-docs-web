"""Unit tests for the ``Structured_Error`` envelope (design D1)."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.core.errors import (
    StructuredError,
    StructuredErrorCode,
    Structured_Error,
)


D1_BASELINE_CODES = {
    "LANGGRAPH_UNAVAILABLE",
    "LANGGRAPH_UPSTREAM_URL_MISSING",
    "CORS_MISCONFIGURED",
    "TRUSTED_HOSTS_MISCONFIGURED",
    "BAD_ARG",
    "SMOKE_TIMEOUT",
    "SMOKE_HTTP_FAIL",
}


def test_alias_matches_class():
    assert Structured_Error is StructuredError


def test_d1_baseline_codes_are_accepted():
    for code in D1_BASELINE_CODES:
        err = StructuredError(code=code, message="hello")
        assert err.code == code


def test_unknown_code_is_rejected():
    with pytest.raises(ValidationError):
        StructuredError(code="DEFINITELY_NOT_A_REAL_CODE", message="boom")


def test_message_must_be_non_empty():
    with pytest.raises(ValidationError):
        StructuredError(code="BAD_ARG", message="")
    with pytest.raises(ValidationError):
        StructuredError(code="BAD_ARG", message="   ")


def test_request_id_defaults_to_uuid():
    err = StructuredError(code="LANGGRAPH_UNAVAILABLE", message="m")
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        err.request_id,
    )


def test_explicit_request_id_is_preserved():
    err = StructuredError(
        code="LANGGRAPH_UNAVAILABLE",
        message="m",
        request_id="my-request-id",
    )
    assert err.request_id == "my-request-id"


def test_request_id_must_be_non_empty():
    with pytest.raises(ValidationError):
        StructuredError(
            code="LANGGRAPH_UNAVAILABLE", message="m", request_id=""
        )


def test_timestamp_default_is_utc_iso_seconds():
    err = StructuredError(code="LANGGRAPH_UNAVAILABLE", message="m")
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", err.timestamp
    )


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        StructuredError(
            code="BAD_ARG", message="m", extra_field="surprise"
        )


def test_model_is_frozen():
    err = StructuredError(code="BAD_ARG", message="m")
    with pytest.raises(ValidationError):
        err.code = "LANGGRAPH_UNAVAILABLE"  # type: ignore[misc]


def test_structured_error_code_literal_is_complete():
    """The Literal alias must include every D1 baseline code."""

    # ``__args__`` is the tuple of allowed Literal values.
    args = set(StructuredErrorCode.__args__)  # type: ignore[attr-defined]
    missing = D1_BASELINE_CODES - args
    assert not missing, f"D1 baseline codes missing from Literal: {missing}"
