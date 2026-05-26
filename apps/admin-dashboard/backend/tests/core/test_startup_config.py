"""Property-based test for startup config validation.

Property 11: Config Validation at Startup.

**Validates: Requirements 14.1, 14.8, 20.4, 20.5, 20.6, 20.7**

For every triple of environment-variable values drawn from the
hypothesis strategies below, the test asserts:

(a) ``app.core.settings.load_settings()`` raises
    :class:`LangGraphUpstreamConfigError` with
    ``code="LANGGRAPH_UPSTREAM_URL_MISSING"`` **iff**
    ``LANGGRAPH_UPSTREAM_URL`` is unset, empty, whitespace, or a
    syntactically invalid ``http``/``https`` URL (R14.1, R14.8).

(b) When the URL is valid, :func:`app.main.create_app` emits a
    structured log record with ``code="CORS_MISCONFIGURED"`` **iff**
    ``CORS_ALLOWED_ORIGINS`` is unset, empty, or unparseable
    (R20.4, R20.5).

(c) When the URL is valid, :func:`app.main.create_app` emits a
    structured log record with ``code="TRUSTED_HOSTS_MISCONFIGURED"``
    **iff** ``TRUSTED_HOSTS`` is unset, empty, or unparseable
    (R20.6, R20.7).

The test runs from ``web/apps/admin-dashboard/backend`` with
``pytest tests/core/test_startup_config.py``.

Strategy notes
--------------
* The strategies match the ones spelled out in the task description so
  the property covers unset / empty / whitespace / malformed / valid
  cases for each variable.  The free-text branches are filtered to drop
  null bytes (which :func:`os.environ` rejects on some platforms) and
  the URL free-text branch additionally drops anything starting with
  ``http`` so the filter contract (per the task description) holds.
* Validity is computed by **independent** oracles
  (:func:`_expect_valid_url`, :func:`_expect_valid_csv`) — they do *not*
  delegate back to the SUT's validators, so a property failure means
  the SUT and the spec definition genuinely disagree rather than the
  test merely echoing the SUT.
"""

from __future__ import annotations

import logging
from typing import Final
from urllib.parse import urlparse

import pytest
from hypothesis import HealthCheck, given, settings as hypo_settings
from hypothesis import strategies as st

from app.core.settings import (
    LangGraphUpstreamConfigError,
    load_settings,
    reset_settings_cache,
)
from app.main import create_app

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Free-text branch for the URL strategy.  We drop strings starting with
# ``http`` so the filter never accidentally yields a *valid* URL via
# the random branch (the task description explicitly requires this
# filter).  Null bytes are stripped because :func:`os.environ` rejects
# them on Windows / POSIX.
_URL_FREE_TEXT = (
    st.text(min_size=1, max_size=80)
    .filter(lambda s: not s.startswith("http") and "\x00" not in s)
)

URL_STRATEGY: Final = st.one_of(
    st.none(),
    st.just(""),
    st.just("   "),
    st.just("ftp://x"),
    st.just("not-a-url"),
    _URL_FREE_TEXT,
    st.just("https://valid.example.com"),
    st.just("http://localhost:8080"),
)

# Shared strategy for ``CORS_ALLOWED_ORIGINS`` and ``TRUSTED_HOSTS``
# (the task description says they are "the same shape").
_CSV_FREE_TEXT = st.text(max_size=80).filter(lambda s: "\x00" not in s)

CSV_STRATEGY: Final = st.one_of(
    st.none(),
    st.just(""),
    st.just("   "),
    st.just(",,,"),
    st.just("https://a.com,https://b.com"),
    _CSV_FREE_TEXT,
)


# ---------------------------------------------------------------------------
# Independent validity oracles
# ---------------------------------------------------------------------------


def _expect_valid_url(value: str | None) -> bool:
    """Truth oracle for ``LANGGRAPH_UPSTREAM_URL`` validity (R14.1).

    A value is valid iff (after stripping whitespace) it parses to an
    ``http`` or ``https`` URL with a non-empty hostname.  This mirrors
    the contract documented in design C10 / R14.1 and is *independent*
    of the SUT's :func:`app.core.settings._is_valid_http_url`.
    """

    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    try:
        parsed = urlparse(stripped)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    return bool(parsed.hostname)


def _expect_valid_csv(value: str | None) -> bool:
    """Truth oracle for the comma-separated allow-list variables.

    A value is "valid" iff at least one comma-separated entry is
    non-blank after stripping whitespace.  This matches the spec
    wording "categorize as 'valid' iff at least one non-blank entry
    parses".
    """

    if value is None:
        return False
    return any(part.strip() for part in value.split(","))


# ---------------------------------------------------------------------------
# Log capture helper
# ---------------------------------------------------------------------------


_APP_MAIN_LOGGER_NAME: Final[str] = "app.main"


class _StructuredErrorCapture(logging.Handler):
    """Collects structured-error codes emitted by :mod:`app.main`.

    ``app.main._log_structured_error`` attaches the structured-error
    payload to the log record via ``extra={"structured_error": ...}``.
    This handler simply records the ``code`` of every payload it sees
    so the test can assert which envelopes were emitted during a
    single :func:`create_app` invocation.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.codes: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        payload = getattr(record, "structured_error", None)
        if isinstance(payload, dict):
            code = payload.get("code")
            if isinstance(code, str):
                self.codes.append(code)


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


@given(url=URL_STRATEGY, cors=CSV_STRATEGY, hosts=CSV_STRATEGY)
@hypo_settings(
    max_examples=100,
    # ``pytest.MonkeyPatch.context()`` is used per example so no
    # function-scoped fixture is touched, but the suppression keeps
    # Hypothesis quiet if a future contributor reaches for caplog or
    # monkeypatch directly.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_startup_config_validation(
    url: str | None, cors: str | None, hosts: str | None
) -> None:
    """**Validates: Requirements 14.1, 14.8, 20.4, 20.5, 20.6, 20.7**

    See the module docstring for the full statement of Property 11.
    """

    expected_url_valid = _expect_valid_url(url)
    expected_cors_valid = _expect_valid_csv(cors)
    expected_hosts_valid = _expect_valid_csv(hosts)

    capture = _StructuredErrorCapture()
    main_logger = logging.getLogger(_APP_MAIN_LOGGER_NAME)
    main_logger.addHandler(capture)
    # Force the logger to emit ERROR records even if a parent handler
    # has filtered them out elsewhere in the test run.
    previous_level = main_logger.level
    if main_logger.level > logging.ERROR or main_logger.level == 0:
        main_logger.setLevel(logging.ERROR)

    try:
        with pytest.MonkeyPatch.context() as mp:
            # --- Apply the env-var triplet -----------------------
            for env_name, value in (
                ("LANGGRAPH_UPSTREAM_URL", url),
                ("CORS_ALLOWED_ORIGINS", cors),
                ("TRUSTED_HOSTS", hosts),
                # ENV has a sensible default; pin it so the cookie
                # branch in ``Settings`` is deterministic across
                # examples and does not depend on the inherited
                # process env.
                ("ENV", "production"),
            ):
                if value is None:
                    mp.delenv(env_name, raising=False)
                else:
                    mp.setenv(env_name, value)

            reset_settings_cache()

            # --- (a) URL validity drives load_settings() -----------
            if not expected_url_valid:
                with pytest.raises(LangGraphUpstreamConfigError) as excinfo:
                    load_settings()
                assert (
                    excinfo.value.structured_error.code
                    == "LANGGRAPH_UPSTREAM_URL_MISSING"
                ), (
                    "load_settings must raise "
                    "LANGGRAPH_UPSTREAM_URL_MISSING for invalid URLs "
                    f"(url={url!r})"
                )
                # Startup terminated; CORS/hosts paths are not
                # reachable on this branch (R14.8 mandates the
                # process exits before binding the HTTP port).
                return

            # URL is valid: load_settings must succeed.
            settings_obj = load_settings()
            assert settings_obj.langgraph_upstream_url, (
                f"valid URL {url!r} must round-trip through Settings"
            )

            # Reset the capture so we observe only what create_app
            # emits for *this* example (load_settings does not log
            # on the success path, but defence in depth).
            capture.codes.clear()

            # --- (b) + (c) CORS / TRUSTED_HOSTS deny-all logging --
            create_app(settings=settings_obj)

            cors_logged = "CORS_MISCONFIGURED" in capture.codes
            hosts_logged = "TRUSTED_HOSTS_MISCONFIGURED" in capture.codes

            assert cors_logged is (not expected_cors_valid), (
                "CORS_MISCONFIGURED log must be emitted iff "
                "CORS_ALLOWED_ORIGINS has no parseable entries "
                f"(cors={cors!r}, expected_valid={expected_cors_valid}, "
                f"codes={capture.codes!r})"
            )
            assert hosts_logged is (not expected_hosts_valid), (
                "TRUSTED_HOSTS_MISCONFIGURED log must be emitted iff "
                "TRUSTED_HOSTS has no parseable entries "
                f"(hosts={hosts!r}, expected_valid={expected_hosts_valid}, "
                f"codes={capture.codes!r})"
            )
    finally:
        main_logger.removeHandler(capture)
        main_logger.setLevel(previous_level)
        reset_settings_cache()
