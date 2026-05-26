"""Property-based test for the supervisor watchdog backoff function.

Property 16: Supervisor Restart-Loop Backoff.

**Validates: Requirements 16.8**

Requirement 16.8 states: while a service has been restarted 5 or more times
within a rolling 60-second window, the supervisor SHALL apply exponential
backoff starting at 10 seconds and capped at 120 seconds before the next
restart attempt. Concretely, design.md Property 16 expresses this as:

    delay(n) = 0                                        if n < 5
             = min(120, 10 * 2 ** (n - 5))              otherwise

The canonical implementation lives in ``scripts/lib/compute_backoff.sh`` (a
sourceable POSIX-shell library extracted from ``scripts/supervisor_watchdog.sh``
in task 12.3 specifically so this property test can verify the same code
the watchdog runs in production). The watchdog ``source``s the same file on
startup, so a parity assertion between Python and the bash function
transitively guarantees the running watchdog satisfies Property 16.

The property is split into two ``@given`` tests so each one can be skipped
independently:

* ``test_watchdog_backoff_python_mirror_matches_formula`` runs on every
  host. It asserts a Python mirror of the bash function equals the closed
  form ``min(120, 10 * 2 ** (n - 5))`` for ``n >= 5`` and ``0`` otherwise,
  catching drift between the documented formula and the implementation
  shape.

* ``test_watchdog_backoff_bash_matches_formula`` shells out to a real
  ``bash`` interpreter and ``source``s ``scripts/lib/compute_backoff.sh``,
  asserting the bash output equals the same formula. This is the test
  that catches a regression in the actual code the watchdog runs. It is
  skipped via ``@pytest.mark.skipif`` when no working ``bash`` is present
  (Windows without WSL, for example), keeping CI green on developer
  machines that cannot host a Linux shell.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------
#
# ``Path(__file__).resolve().parents[N]`` walks up the on-disk layout:
#
#   0 -> tests/scripts
#   1 -> tests
#   2 -> backend                              (admin-dashboard backend root)
#   3 -> admin-dashboard
#   4 -> apps
#   5 -> web
#   6 -> repository root
#
# Resolving once at import time means both @given tests and the bash
# skip predicate all see the same canonical paths.

_THIS_FILE: Path = Path(__file__).resolve()
_REPO_ROOT: Path = _THIS_FILE.parents[6]
_BACKOFF_LIB: Path = _REPO_ROOT / "scripts" / "lib" / "compute_backoff.sh"


# ---------------------------------------------------------------------------
# Canonical formula and Python mirror of compute_backoff_delay
# ---------------------------------------------------------------------------
#
# The bash function in ``scripts/lib/compute_backoff.sh`` clamps the
# exponent at 30 to stay inside 32-bit signed arithmetic. Any exponent
# >= 5 already exceeds the 120-second MAX_DELAY, so the cap is what
# observably governs the output for large n -- the exponent clamp is
# defensive and never changes the returned value. We mirror it anyway
# so the Python implementation tracks the bash one byte for byte.

_RESTART_THRESHOLD: int = 5
_BASE_DELAY: int = 10
_MAX_DELAY: int = 120
_EXPONENT_CAP: int = 30


def _expected_formula(n: int) -> int:
    """Return the design.md / R16.8 closed-form expected delay for ``n``.

    Spelled out without the exponent guard so the formula is self-evident
    when read alongside the requirement text. Python ints are arbitrary
    precision, so ``2 ** (n - 5)`` is safe for the strategy's upper bound.
    """
    if n < _RESTART_THRESHOLD:
        return 0
    return min(_MAX_DELAY, _BASE_DELAY * (2 ** (n - _RESTART_THRESHOLD)))


def _python_compute_backoff_delay(count: int) -> int:
    """Python translation of ``compute_backoff_delay`` from the bash lib.

    Keeping the structure (early-return, exponent clamp, post-multiply cap)
    parallel to the bash function makes it cheap to spot drift between the
    two implementations during code review.
    """
    if count < _RESTART_THRESHOLD:
        return 0
    exponent = count - _RESTART_THRESHOLD
    if exponent > _EXPONENT_CAP:
        exponent = _EXPONENT_CAP
    delay = _BASE_DELAY * (1 << exponent)
    if delay > _MAX_DELAY:
        delay = _MAX_DELAY
    return delay


# ---------------------------------------------------------------------------
# Bash interop
# ---------------------------------------------------------------------------
#
# Sourcing the watchdog script directly is unsafe (its body runs ``main``
# which calls ``docker``), so the backoff function lives in a standalone
# library file that is pure: sourcing it only declares the function and
# default values. Both the watchdog and this test source the same file,
# so a parity assertion here transitively guarantees the running watchdog
# matches the property under test.


def _resolve_usable_bash() -> str | None:
    """Return a path to a working ``bash`` interpreter, or ``None``.

    ``shutil.which("bash")`` may return a path on Windows that points at a
    WSL stub which fails to launch (no Linux distribution installed). We
    probe with ``bash -c "true"`` and treat any non-zero exit, ``OSError``,
    or timeout as "no usable bash here". This mirrors the same probe used
    by ``tests/migrations/test_round_trip.py`` so both PBT tests skip
    consistently across the supported developer environments.
    """
    candidate = shutil.which("bash")
    if candidate is None:
        return None
    try:
        probe = subprocess.run(
            [candidate, "-c", "true"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return candidate if probe.returncode == 0 else None


_BASH: str | None = _resolve_usable_bash()


def _bash_compute_backoff_delay(bash_path: str, count: int) -> int:
    """Invoke the real bash ``compute_backoff_delay`` and return its output.

    We source ``scripts/lib/compute_backoff.sh`` rather than
    ``scripts/supervisor_watchdog.sh`` because the latter executes its
    ``main`` body on source (it is a script, not a library). The library
    file is purpose-built to be sourceable: defining the function and
    default thresholds with no side effects.
    """
    cmd = [
        bash_path,
        "-c",
        f'source "{_BACKOFF_LIB.as_posix()}"; compute_backoff_delay {count}',
    ]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, (
        "bash compute_backoff_delay exited non-zero\n"
        f"  count     : {count}\n"
        f"  exit_code : {completed.returncode}\n"
        f"  stdout    :\n{completed.stdout}\n"
        f"  stderr    :\n{completed.stderr}\n"
    )
    output = completed.stdout.strip()
    return int(output)


# ---------------------------------------------------------------------------
# The properties
# ---------------------------------------------------------------------------
#
# Hypothesis pool for both tests: integers in [0, 200].
#
# * 0..4 covers the n < threshold branch (delay must be 0).
# * 5..N covers the active branch where the formula min(120, 10 * 2^(n-5))
#   should hold, including exponent values that overflow naive 64-bit
#   arithmetic if the cap or guard ever regressed.
#
# The 200 upper bound is well past the point where the formula has been
# saturated at MAX_DELAY for hundreds of doublings, exercising the
# exponent-clamp branch in both implementations on every run.

_BACKOFF_LIB_MISSING_REASON = (
    f"backoff library missing at {_BACKOFF_LIB}; "
    "expected scripts/lib/compute_backoff.sh from task 12.3."
)


@pytest.mark.skipif(not _BACKOFF_LIB.is_file(), reason=_BACKOFF_LIB_MISSING_REASON)
@given(n=st.integers(min_value=0, max_value=200))
@settings(max_examples=100, deadline=None)
def test_watchdog_backoff_python_mirror_matches_formula(n: int) -> None:
    """**Validates: Requirements 16.8**

    For every ``n`` in [0, 200], the Python mirror of
    ``compute_backoff_delay`` SHALL produce ``0`` for ``n < 5`` and
    ``min(120, 10 * 2 ** (n - 5))`` otherwise. This test runs on every
    host so the formula is continuously asserted regardless of whether a
    bash interpreter is installed.
    """
    expected = _expected_formula(n)

    # Branch invariants spelled out so a failure points to the specific
    # clause of R16.8 that broke.
    if n < _RESTART_THRESHOLD:
        assert expected == 0, (
            f"formula self-check: n={n} < {_RESTART_THRESHOLD} should yield 0, "
            f"got {expected}"
        )
    else:
        assert expected <= _MAX_DELAY, (
            f"formula self-check: n={n} produced {expected}s which exceeds "
            f"MAX_DELAY={_MAX_DELAY}s"
        )
        assert expected >= _BASE_DELAY, (
            f"formula self-check: n={n} produced {expected}s which is below "
            f"BASE_DELAY={_BASE_DELAY}s"
        )

    python_value = _python_compute_backoff_delay(n)
    assert python_value == expected, (
        "Python mirror of compute_backoff_delay diverged from the "
        "Requirement 16.8 formula\n"
        f"  n        : {n}\n"
        f"  expected : {expected}\n"
        f"  python   : {python_value}\n"
    )


@pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="bash interpreter not on PATH; cannot exercise the real watchdog function.",
)
@pytest.mark.skipif(
    _BASH is None,
    reason=(
        "bash interpreter present but unusable on this host (Windows without "
        "an installed WSL distribution, for example); cannot exercise the "
        "real watchdog function."
    ),
)
@pytest.mark.skipif(not _BACKOFF_LIB.is_file(), reason=_BACKOFF_LIB_MISSING_REASON)
@given(n=st.integers(min_value=0, max_value=200))
@settings(max_examples=100, deadline=None)
def test_watchdog_backoff_bash_matches_formula(n: int) -> None:
    """**Validates: Requirements 16.8**

    For every ``n`` in [0, 200], the bash function ``compute_backoff_delay``
    sourced from ``scripts/lib/compute_backoff.sh`` SHALL produce the same
    value as ``min(120, 10 * 2 ** (n - 5))`` for ``n >= 5`` and ``0``
    otherwise. Because the production watchdog (``scripts/supervisor_watchdog.sh``)
    sources the same library file, a passing run here certifies the
    running watchdog satisfies Property 16.
    """
    # ``skipif`` already rules these out, but keep the invariant locally
    # explicit so a future refactor that drops a guard fails loudly
    # instead of silently running garbage.
    assert _BASH is not None, "skipif should have prevented entry without bash"

    expected = _expected_formula(n)
    bash_value = _bash_compute_backoff_delay(_BASH, n)
    assert bash_value == expected, (
        "bash compute_backoff_delay diverged from Requirement 16.8\n"
        f"  n        : {n}\n"
        f"  expected : {expected}\n"
        f"  bash     : {bash_value}\n"
        f"  source   : {_BACKOFF_LIB}\n"
    )
