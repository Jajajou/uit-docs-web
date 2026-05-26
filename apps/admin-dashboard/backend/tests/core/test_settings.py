"""Unit tests for ``app.core.settings`` (design C10, C15)."""

from __future__ import annotations

import pytest

from app.core.errors import StructuredError
from app.core.settings import (
    LangGraphUpstreamConfigError,
    Settings,
    load_settings,
    reset_settings_cache,
)


VALID_URL = "https://langgraph.example.com"


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip any inherited values so each test runs in a clean env."""

    for key in (
        "LANGGRAPH_UPSTREAM_URL",
        "CORS_ALLOWED_ORIGINS",
        "TRUSTED_HOSTS",
        "ENV",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()


# ---------------------------------------------------------------------------
# LANGGRAPH_UPSTREAM_URL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://lang.example.com",
        "http://localhost:2024",
        "https://lang.example.com/health",
        "http://10.0.0.5:8080/api",
    ],
)
def test_valid_langgraph_url_is_accepted(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", url)
    settings = load_settings()
    assert settings.langgraph_upstream_url == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "ftp://example.com",
        "not-a-url",
        "http://",
        "https://",
        "://no-scheme",
    ],
)
def test_invalid_langgraph_url_raises_structured_error(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", url)
    with pytest.raises(LangGraphUpstreamConfigError) as excinfo:
        load_settings()
    err: StructuredError = excinfo.value.structured_error
    assert err.code == "LANGGRAPH_UPSTREAM_URL_MISSING"
    assert err.message
    assert err.request_id
    assert err.timestamp


def test_unset_langgraph_url_raises_structured_error() -> None:
    # autouse fixture has already deleted the var.
    with pytest.raises(LangGraphUpstreamConfigError) as excinfo:
        load_settings()
    assert excinfo.value.structured_error.code == "LANGGRAPH_UPSTREAM_URL_MISSING"


def test_langgraph_url_is_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "LANGGRAPH_UPSTREAM_URL", "  https://lang.example.com  "
    )
    settings = load_settings()
    assert settings.langgraph_upstream_url == "https://lang.example.com"


# ---------------------------------------------------------------------------
# CORS_ALLOWED_ORIGINS
# ---------------------------------------------------------------------------


def test_cors_origins_parsed_from_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://a.example.com, https://b.example.com ,https://c.example.com",
    )
    settings = load_settings()
    assert settings.cors_allowed_origins == [
        "https://a.example.com",
        "https://b.example.com",
        "https://c.example.com",
    ]
    assert settings.cors_misconfigured() is False


@pytest.mark.parametrize("raw", ["", "   ", ", , ,"])
def test_cors_misconfigured_helper(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", raw)
    settings = load_settings()
    assert settings.cors_allowed_origins == []
    assert settings.cors_misconfigured() is True


def test_cors_unset_is_misconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    settings = load_settings()
    assert settings.cors_misconfigured() is True


# ---------------------------------------------------------------------------
# TRUSTED_HOSTS
# ---------------------------------------------------------------------------


def test_trusted_hosts_parsed_from_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    monkeypatch.setenv(
        "TRUSTED_HOSTS", "admin.example.com,admin.example.org"
    )
    settings = load_settings()
    assert settings.trusted_hosts == [
        "admin.example.com",
        "admin.example.org",
    ]
    assert settings.trusted_hosts_misconfigured() is False


@pytest.mark.parametrize("raw", ["", "   ", ", ,"])
def test_trusted_hosts_misconfigured_helper(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    monkeypatch.setenv("TRUSTED_HOSTS", raw)
    settings = load_settings()
    assert settings.trusted_hosts == []
    assert settings.trusted_hosts_misconfigured() is True


# ---------------------------------------------------------------------------
# ENV
# ---------------------------------------------------------------------------


def test_env_defaults_to_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    settings = load_settings()
    assert settings.env == "production"
    assert settings.is_production() is True


@pytest.mark.parametrize(
    "raw,expected,is_prod",
    [
        ("staging", "staging", False),
        ("dev", "dev", False),
        ("PRODUCTION", "production", True),
        ("  Staging  ", "staging", False),
    ],
)
def test_env_normalised(
    raw: str,
    expected: str,
    is_prod: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGGRAPH_UPSTREAM_URL", VALID_URL)
    monkeypatch.setenv("ENV", raw)
    settings = load_settings()
    assert settings.env == expected
    assert settings.is_production() is is_prod


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def test_explicit_overrides_take_precedence() -> None:
    settings = Settings(LANGGRAPH_UPSTREAM_URL=VALID_URL)  # type: ignore[arg-type]
    assert settings.langgraph_upstream_url == VALID_URL


def test_load_settings_overrides_bypass_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Even with the env var unset/missing, an override unblocks
    # construction.
    settings = load_settings(LANGGRAPH_UPSTREAM_URL=VALID_URL)
    assert settings.langgraph_upstream_url == VALID_URL
