"""Property-based test for the smoke test script contract.

Property 10: Smoke Test Contract.

**Validates: Requirements 18.1, 18.2, 18.3, 18.4**

For any triple of URLs ``(F, B, U)`` and any combination of mocked HTTP
outcomes for the probes ``B/healthz``, ``F/``, ``U/health``, the script
``scripts/smoke_test.sh --frontend-url F --backend-url B --upstream-url U``
SHALL exit 0 if and only if all three probes complete with HTTP status in
``[200, 299]`` within their per-request 5-second budget AND the total
elapsed time is at most 30 seconds; otherwise it SHALL exit 1 and print
exactly one ``Structured_Error`` JSON line to stdout naming the
first-failing URL, its observed status (or ``"timeout"``), and elapsed
milliseconds.

Strategy:

* Hypothesis draws one outcome per probe from
  ``sampled_from([200, 201, 299, 300, 404, 500, 503, "timeout", "close"])``.
* Each example spins up three local HTTP servers on random free ports
  bound to ``127.0.0.1``. Each server is configured with the drawn
  outcome:

  - integer ``2xx``/``3xx``/``4xx``/``5xx``: respond with that status;
  - ``"timeout"``: sleep longer than curl's per-request 5-second budget
    so curl exits ``28`` (``CURLE_OPERATION_TIMEDOUT``);
  - ``"close"``: shut the socket before writing any response so curl
    exits with one of the connection-error codes (52, 56, ...).

* The script is invoked via ``subprocess.run`` with a per-example
  60-second timeout. ``max_examples=20`` because each example can wait
  up to ~5s for the timeout outcome and we want predictable wall-clock
  cost.
* The expected ``(exit_code, code, status, url)`` are computed from a
  small reference function that mirrors the deterministic
  backend → frontend → upstream first-failure order documented in the
  script. The reference function does not call into the script.

This file lives at::

    web/apps/admin-dashboard/backend/tests/scripts/test_smoke_test.py

so ``parents[6]`` of this file is the repository root, where the script
under test resides at ``scripts/smoke_test.sh``.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import threading
import time
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Locate the script under test
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[6]
_SCRIPT_PATH: Path = _REPO_ROOT / "scripts" / "smoke_test.sh"

assert _SCRIPT_PATH.is_file(), (
    f"smoke_test.sh not found at expected path {_SCRIPT_PATH}; "
    "task 8.1 must produce this script before task 8.2 can validate it"
)


# ---------------------------------------------------------------------------
# Bash discovery
# ---------------------------------------------------------------------------


def _find_working_bash() -> str | None:
    """Return the path to a bash interpreter that actually works.

    On Windows, ``shutil.which("bash")`` may resolve to the WSL stub
    (``C:\\Windows\\System32\\bash.exe``) which only succeeds when a
    Linux distro has been installed. Probe each candidate with a trivial
    command so a broken stub does not silently fail every example.
    Common Git-for-Windows install paths are tried as fallbacks.
    """
    candidates: list[str] = []
    primary = shutil.which("bash")
    if primary:
        candidates.append(primary)
    for fallback in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        r"C:\laragon\bin\git\bin\bash.exe",
        "/usr/bin/bash",
        "/bin/bash",
    ):
        if fallback in candidates:
            continue
        if Path(fallback).is_file():
            candidates.append(fallback)
    for cand in candidates:
        try:
            r = subprocess.run(
                [cand, "-c", "echo ok"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0 and r.stdout.strip() == "ok":
            return cand
    return None


_BASH: str | None = _find_working_bash()


# ---------------------------------------------------------------------------
# Mock HTTP server
# ---------------------------------------------------------------------------


# Outcomes are either an HTTP status code (int) or one of the categorical
# strings "timeout" / "close". Drawn from the per-probe Hypothesis
# strategy below.
_OUTCOMES: list[object] = [200, 201, 299, 300, 404, 500, 503, "timeout", "close"]


class _MockHandler(BaseHTTPRequestHandler):
    """HTTP handler whose behaviour is driven by ``self.server.outcome``.

    A single handler class drives all three mock servers — each server
    instance carries its own configured outcome.
    """

    # silence access logs (would otherwise spam stderr during runs)
    def log_message(self, format, *args):  # noqa: A002, ARG002
        return

    def _respond(self) -> None:
        outcome = getattr(self.server, "outcome", 200)

        if outcome == "timeout":
            # Sleep longer than curl's --max-time 5 so curl exits 28
            # (CURLE_OPERATION_TIMEDOUT). 6s leaves headroom but stays
            # well below the per-example 60s subprocess timeout.
            time.sleep(6.0)
            try:
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError, OSError):
                # Client likely already gave up — that's the whole point
                # of this branch. Swallow the error so the handler thread
                # exits cleanly.
                pass
            return

        if outcome == "close":
            # Close the socket without sending any HTTP response. curl
            # exits non-zero with one of CURLE_GOT_NOTHING (52),
            # CURLE_RECV_ERROR (56) or CURLE_SEND_ERROR (55) depending
            # on platform/timing. The script maps any unrecognised curl
            # exit to SMOKE_HTTP_FAIL via its catch-all ``*)`` branch.
            self.close_connection = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            return

        # Integer status code — write headers only, empty body.
        status = int(outcome)  # type: ignore[arg-type]
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._respond()

    def do_HEAD(self) -> None:  # noqa: N802
        self._respond()


class _MockServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that releases handler threads on shutdown."""

    daemon_threads = True
    allow_reuse_address = True


@contextmanager
def _start_mock_server(outcome: object) -> Iterator[str]:
    """Start a mock HTTP server bound to a random localhost port.

    Yields the base URL (no trailing slash). The server is shut down on
    context exit; the handler thread is a daemon so any in-flight
    ``time.sleep`` from the timeout branch will not block teardown.
    """
    server = _MockServer(("127.0.0.1", 0), _MockHandler)
    server.outcome = outcome  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        try:
            server.shutdown()
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            server.server_close()
        except Exception:  # pragma: no cover - defensive
            pass
        thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Reference oracle
# ---------------------------------------------------------------------------


def _expected_outcome(
    backend: object,
    frontend: object,
    upstream: object,
) -> tuple[int, str | None, str | None, str | None]:
    """Compute ``(exit_code, label, code, status_field)`` per Property 10.

    Mirrors the script's deterministic ordering: backend → frontend →
    upstream. Returns ``(0, None, None, None)`` on full success.

    ``status_field`` is the value the script will place in
    ``Structured_Error.status`` for the first failing probe — exactly
    ``"timeout"`` for a timeout, the integer code as a string for a
    non-2xx HTTP response, and ``None`` (do not check) for a
    closed-connection failure whose curl exit code varies by platform.
    """
    for label, outcome in (
        ("backend", backend),
        ("frontend", frontend),
        ("upstream", upstream),
    ):
        if isinstance(outcome, int) and 200 <= outcome <= 299:
            continue
        if outcome == "timeout":
            return 1, label, "SMOKE_TIMEOUT", "timeout"
        if outcome == "close":
            # Don't pin the exact curl-exit sentinel; the contract only
            # requires SMOKE_HTTP_FAIL.
            return 1, label, "SMOKE_HTTP_FAIL", None
        # 300..599 non-2xx
        return 1, label, "SMOKE_HTTP_FAIL", str(outcome)
    return 0, None, None, None


def _label_to_url_suffix(label: str) -> str:
    return {
        "backend": "/healthz",
        "frontend": "/",
        "upstream": "/health",
    }[label]


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


_outcome_strategy = st.sampled_from(_OUTCOMES)


@pytest.mark.skipif(_BASH is None, reason="bash unavailable")
@given(
    backend=_outcome_strategy,
    frontend=_outcome_strategy,
    upstream=_outcome_strategy,
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_smoke_test_contract(
    backend: object, frontend: object, upstream: object
) -> None:
    """**Validates: Requirements 18.1, 18.2, 18.3, 18.4**

    Exit 0 ⇔ all three probes returned 2xx within budget AND no JSON
    output. Exit 1 ⇔ at least one failure AND exactly one
    ``Structured_Error`` JSON line on stdout naming the first-failing
    probe URL with the appropriate code.
    """
    assert _BASH is not None  # narrow for type checkers; guarded by skipif

    with ExitStack() as stack:
        backend_url = stack.enter_context(_start_mock_server(backend))
        frontend_url = stack.enter_context(_start_mock_server(frontend))
        upstream_url = stack.enter_context(_start_mock_server(upstream))

        result = subprocess.run(
            [
                _BASH,
                str(_SCRIPT_PATH),
                "--backend-url",
                backend_url,
                "--frontend-url",
                frontend_url,
                "--upstream-url",
                upstream_url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

    expected_rc, label, expected_code, expected_status = _expected_outcome(
        backend, frontend, upstream
    )

    assert result.returncode == expected_rc, (
        "smoke_test.sh exit code disagrees with Property 10 contract.\n"
        f"  outcomes = backend={backend!r} frontend={frontend!r} "
        f"upstream={upstream!r}\n"
        f"  expected_rc = {expected_rc}\n"
        f"  actual_rc = {result.returncode}\n"
        f"  stdout = {result.stdout!r}\n"
        f"  stderr = {result.stderr!r}"
    )

    if expected_rc == 0:
        # Silent success: no stdout per R18.1.
        assert result.stdout.strip() == "", (
            "Successful run must produce no stdout per R18.1.\n"
            f"  stdout = {result.stdout!r}"
        )
        return

    # Failure: exactly one Structured_Error JSON line on stdout.
    stdout_lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(stdout_lines) == 1, (
        "Failure run must produce exactly one Structured_Error JSON line "
        "on stdout.\n"
        f"  outcomes = backend={backend!r} frontend={frontend!r} "
        f"upstream={upstream!r}\n"
        f"  stdout = {result.stdout!r}"
    )

    try:
        payload = json.loads(stdout_lines[0])
    except json.JSONDecodeError as exc:  # pragma: no cover - failure trace
        raise AssertionError(
            f"Structured_Error stdout is not valid JSON: {exc}\n"
            f"  line = {stdout_lines[0]!r}"
        )

    assert payload.get("code") == expected_code, (
        "Structured_Error.code mismatch.\n"
        f"  outcomes = backend={backend!r} frontend={frontend!r} "
        f"upstream={upstream!r}\n"
        f"  expected = {expected_code!r}\n"
        f"  actual   = {payload.get('code')!r}\n"
        f"  payload  = {payload!r}"
    )

    assert label is not None  # implied by expected_rc == 1
    expected_url_suffix = _label_to_url_suffix(label)
    actual_url = payload.get("url", "")
    assert isinstance(actual_url, str) and actual_url.endswith(
        expected_url_suffix
    ), (
        "Structured_Error.url should name the first-failing probe URL.\n"
        f"  outcomes = backend={backend!r} frontend={frontend!r} "
        f"upstream={upstream!r}\n"
        f"  expected suffix = {expected_url_suffix!r}\n"
        f"  payload.url     = {actual_url!r}\n"
        f"  failing label   = {label}"
    )

    if expected_status is not None:
        assert payload.get("status") == expected_status, (
            "Structured_Error.status mismatch.\n"
            f"  expected = {expected_status!r}\n"
            f"  actual   = {payload.get('status')!r}\n"
            f"  payload  = {payload!r}"
        )

    assert "elapsed_ms" in payload, (
        "Structured_Error must include elapsed_ms.\n"
        f"  payload = {payload!r}"
    )
    elapsed_ms = payload["elapsed_ms"]
    assert isinstance(elapsed_ms, int) and elapsed_ms >= 0, (
        f"elapsed_ms must be a non-negative integer; payload = {payload!r}"
    )
