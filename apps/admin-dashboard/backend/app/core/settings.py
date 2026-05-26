"""Pydantic Settings for ``Admin_Backend`` (design C10, C15).

This module reads the four environment variables required by the
``cicd-deploy-admin-dashboard`` spec:

* ``LANGGRAPH_UPSTREAM_URL`` — the LangGraph upstream base URL (R14.1, R14.8).
* ``CORS_ALLOWED_ORIGINS`` — comma-separated list (R20.4, R20.5).
* ``TRUSTED_HOSTS`` — comma-separated list (R20.6, R20.7).
* ``ENV`` — environment label, used by ``app.core.security`` to decide
  cookie hardening (R20.3).

The :class:`Settings` model raises
:class:`LangGraphUpstreamConfigError` when ``LANGGRAPH_UPSTREAM_URL`` is
unset, empty, or syntactically not an ``http``/``https`` URL.  The
exception carries a fully formed
:class:`~app.core.errors.Structured_Error` with
``code="LANGGRAPH_UPSTREAM_URL_MISSING"`` so that the FastAPI
``lifespan`` startup guard wired in task 9.4 can log it once and exit
non-zero before binding the HTTP port.

For ``CORS_ALLOWED_ORIGINS`` and ``TRUSTED_HOSTS`` the model never raises
on parse failure — it instead exposes
:meth:`Settings.cors_misconfigured` and
:meth:`Settings.trusted_hosts_misconfigured` helpers plus the parsed
list properties.  Task 10.1 wires the deny-all middlewares from those
helpers; this task only sets up the model.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import StructuredError

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LangGraphUpstreamConfigError(RuntimeError):
    """Raised when ``LANGGRAPH_UPSTREAM_URL`` fails validation at startup.

    The exception wraps a :class:`Structured_Error` with
    ``code="LANGGRAPH_UPSTREAM_URL_MISSING"`` so the startup guard can
    log the envelope and exit non-zero before binding the HTTP port
    (R14.8).
    """

    def __init__(self, error: StructuredError) -> None:
        if error.code != "LANGGRAPH_UPSTREAM_URL_MISSING":
            raise ValueError(
                "LangGraphUpstreamConfigError requires code "
                "'LANGGRAPH_UPSTREAM_URL_MISSING', "
                f"got {error.code!r}"
            )
        self.structured_error = error
        super().__init__(error.message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


EnvName = Literal["production", "staging", "dev", "development", "test", "ci"]


def _parse_csv(raw: str | None) -> list[str]:
    """Split a comma-separated string into a list of trimmed entries.

    Empty strings and whitespace-only entries are dropped.  ``None`` is
    treated as the empty list.
    """

    if raw is None:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _is_valid_http_url(value: str) -> bool:
    """Return ``True`` iff ``value`` is a syntactically valid http/https URL.

    ``http(s)://host[:port][/path...]`` is accepted; everything else is
    rejected.  The check uses :func:`urllib.parse.urlparse` and confirms
    both a recognised scheme and a non-empty host.
    """

    if not value or not value.strip():
        return False
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    # ``urlparse`` happily accepts ``http://``; ensure a real host part is
    # present (``netloc`` for ``http://`` is the empty string already
    # handled above, but ``http://:8080`` would slip through).
    if not parsed.hostname:
        return False
    return True


# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Application settings used by the production-hardening features.

    Field semantics:

    * ``langgraph_upstream_url`` (env ``LANGGRAPH_UPSTREAM_URL``) — must
      be a non-empty ``http``/``https`` URL; otherwise the constructor
      raises :class:`LangGraphUpstreamConfigError`.
    * ``cors_allowed_origins_raw`` (env ``CORS_ALLOWED_ORIGINS``) —
      comma-separated string preserved verbatim; parsed via
      :pyattr:`cors_allowed_origins`.
    * ``trusted_hosts_raw`` (env ``TRUSTED_HOSTS``) — comma-separated
      string preserved verbatim; parsed via :pyattr:`trusted_hosts`.
    * ``env`` (env ``ENV``) — environment label, defaults to
      ``"production"`` so misconfigured deployments fail closed.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    langgraph_upstream_url: str = Field(
        default="",
        validation_alias="LANGGRAPH_UPSTREAM_URL",
        description="LangGraph upstream base URL (R14.1, R14.8).",
    )
    cors_allowed_origins_raw: str = Field(
        default="",
        validation_alias="CORS_ALLOWED_ORIGINS",
        description="Comma-separated allow-list (R20.4, R20.5).",
    )
    trusted_hosts_raw: str = Field(
        default="",
        validation_alias="TRUSTED_HOSTS",
        description="Comma-separated allow-list (R20.6, R20.7).",
    )
    env: str = Field(
        default="production",
        validation_alias="ENV",
        description="Environment label; controls cookie hardening (R20.3).",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("langgraph_upstream_url", mode="before")
    @classmethod
    def _coerce_langgraph_upstream_url(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @field_validator("langgraph_upstream_url")
    @classmethod
    def _validate_langgraph_upstream_url(cls, value: str) -> str:
        if not _is_valid_http_url(value):
            # Build the structured error here so the message clearly
            # describes which condition failed.
            if not value:
                message = (
                    "LANGGRAPH_UPSTREAM_URL is unset or empty; "
                    "Admin_Backend cannot start."
                )
            else:
                message = (
                    "LANGGRAPH_UPSTREAM_URL is not a syntactically valid "
                    "http(s) URL; Admin_Backend cannot start."
                )
            structured = StructuredError(
                code="LANGGRAPH_UPSTREAM_URL_MISSING",
                message=message,
            )
            raise LangGraphUpstreamConfigError(structured)
        return value

    @field_validator("env", mode="before")
    @classmethod
    def _normalise_env(cls, value: object) -> str:
        if value is None:
            return "production"
        text = str(value).strip().lower()
        return text or "production"

    # ------------------------------------------------------------------
    # Derived properties (parsed lists + misconfiguration helpers)
    # ------------------------------------------------------------------

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Parsed list of CORS origins (R20.4)."""

        return _parse_csv(self.cors_allowed_origins_raw)

    @property
    def trusted_hosts(self) -> list[str]:
        """Parsed list of trusted hosts (R20.6)."""

        return _parse_csv(self.trusted_hosts_raw)

    def cors_misconfigured(self) -> bool:
        """``True`` iff ``CORS_ALLOWED_ORIGINS`` is unset/empty/unparseable.

        Task 10.1 wires this into a deny-all CORS handler that returns
        HTTP 403 + a structured log with ``code=CORS_MISCONFIGURED``
        (R20.5).
        """

        return len(self.cors_allowed_origins) == 0

    def trusted_hosts_misconfigured(self) -> bool:
        """``True`` iff ``TRUSTED_HOSTS`` is unset/empty/unparseable.

        Task 10.1 wires this into a deny-all trusted-host handler that
        returns HTTP 400 + a structured log with
        ``code=TRUSTED_HOSTS_MISCONFIGURED`` (R20.7).
        """

        return len(self.trusted_hosts) == 0

    def is_production(self) -> bool:
        """Return ``True`` when ``ENV`` is the literal ``production``.

        Task 10.1 / R20.3 use this gate to enable secure cookie
        attributes.
        """

        return self.env == "production"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_settings(**overrides: object) -> Settings:
    """Build a :class:`Settings` instance from the current process env.

    ``overrides`` are passed straight to the :class:`Settings`
    constructor — useful for tests that want to inject a value without
    touching ``os.environ``.

    Pydantic wraps validator exceptions inside a ``ValidationError``.
    We unwrap it so callers (and the lifespan startup guard wired in
    task 9.4) see the original :class:`LangGraphUpstreamConfigError`
    directly, complete with its embedded :class:`Structured_Error`.
    """

    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        for error in exc.errors():
            ctx = error.get("ctx") or {}
            inner = ctx.get("error")
            if isinstance(inner, LangGraphUpstreamConfigError):
                raise inner from exc
        raise


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance.

    The cache mirrors the design's "read once at startup" requirement
    (R14.1).  Tests that mutate ``os.environ`` should call
    :func:`get_settings.cache_clear` to force a re-read.
    """

    return load_settings()


def reset_settings_cache() -> None:
    """Clear the :func:`get_settings` cache (test helper)."""

    get_settings.cache_clear()


__all__ = [
    "EnvName",
    "LangGraphUpstreamConfigError",
    "Settings",
    "get_settings",
    "load_settings",
    "reset_settings_cache",
]


# ---------------------------------------------------------------------------
# Environment override hook
# ---------------------------------------------------------------------------
# ``BaseSettings`` reads ``os.environ`` lazily through pydantic-settings'
# source chain.  We deliberately do **not** auto-construct a settings
# instance at import time so that test harnesses that import this
# module without setting ``LANGGRAPH_UPSTREAM_URL`` (e.g. unrelated unit
# tests) don't blow up.  Callers that need the validated settings must
# go through :func:`get_settings` or :func:`load_settings`.
