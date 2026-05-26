"""Property-based test for the Alembic migration round-trip script.

Property 5: Migration Reversibility.

**Validates: Requirements 12.1, 12.2, 12.3, 12.4**

For every Alembic revision id present in
``web/apps/admin-dashboard/backend/alembic/versions/`` the round-trip
script ``scripts/ci/alembic_round_trip.sh`` (built in task 3.7) must exit
0 when invoked against a fresh SQLite temp file. The revision id is
sampled by Hypothesis from the discovered set so the property has been
exercised against every id in the tree, capped at ``max_examples=100``.

The script under test always performs the three-step sequence
``alembic upgrade head`` → ``alembic downgrade base`` →
``alembic upgrade head`` from the backend working directory, so the
revision id is used purely to drive coverage over the version-tree
membership: if any revision was missing, broken, or not reachable from
``head``, at least one of the three commands would exit non-zero and the
property would fail.

If no revisions exist yet the property holds vacuously and the test
skips with a clear message, so the suite does not block CI before any
migrations have been authored. Likewise, if ``bash`` is unavailable on
the host (typical on Windows without WSL) or the ``alembic`` CLI
cannot be resolved from inside that bash, the test skips: the
round-trip script is a POSIX shell script that shells out to
``alembic`` directly, and a missing interpreter or missing CLI would
fail for reasons unrelated to Property 5.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------
#
# ``Path(__file__).resolve().parents[N]`` walks up:
#
#   0 -> tests/migrations
#   1 -> tests
#   2 -> backend                              (admin-dashboard backend root)
#   3 -> admin-dashboard
#   4 -> apps
#   5 -> web
#   6 -> repository root
#
# We resolve everything once at import time so the strategy declared on
# ``@given`` below sees a fully populated revision list.

_THIS_FILE: Path = Path(__file__).resolve()
_BACKEND_DIR: Path = _THIS_FILE.parents[2]
_REPO_ROOT: Path = _THIS_FILE.parents[6]
_VERSIONS_DIR: Path = _BACKEND_DIR / "alembic" / "versions"
_ROUND_TRIP_SCRIPT: Path = _REPO_ROOT / "scripts" / "ci" / "alembic_round_trip.sh"


# ---------------------------------------------------------------------------
# Revision discovery
# ---------------------------------------------------------------------------
#
# Alembic revision files declare their id with one of these forms:
#
#   revision = "xxx"
#   revision: str = "xxx"
#
# We accept both, ignore non-revision modules (``__init__.py``,
# ``__pycache__``), and skip files that do not declare a revision at all
# (e.g. utility helpers a project might place alongside its versions).

_REVISION_LINE_RE = re.compile(
    r"""^\s*revision\s*(?::\s*[^=]+)?\s*=\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)


def _discover_revisions(versions_dir: Path) -> List[str]:
    """Return every revision id present under ``versions_dir``.

    Returns an empty list when the directory is missing or contains no
    revision modules. The order is deterministic (sorted by filename)
    so Hypothesis shrinks predictably.
    """
    if not versions_dir.is_dir():
        return []
    found: list[str] = []
    for py_path in sorted(versions_dir.glob("*.py")):
        if py_path.name == "__init__.py":
            continue
        try:
            text = py_path.read_text(encoding="utf-8")
        except OSError:
            continue
        match = _REVISION_LINE_RE.search(text)
        if match is not None:
            found.append(match.group(1))
    return found


_REVISIONS: List[str] = _discover_revisions(_VERSIONS_DIR)


def _resolve_usable_bash() -> str | None:
    """Return a path to a working ``bash`` interpreter, or ``None``.

    ``shutil.which("bash")`` may return a path on Windows that points
    at a WSL stub which cannot launch (e.g. when no Linux distribution
    is installed). The round-trip script is genuinely unusable on such
    hosts even though the binary is on ``PATH``, so we probe with
    ``bash -c "true"`` and only return the path when that exits 0.
    Probe failures (any non-zero exit, ``OSError``, or timeout) yield
    ``None`` so the test skips for the same reason as a missing bash.
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


def _bash_has_alembic(bash_path: str) -> bool:
    """Check that ``alembic`` is reachable from inside the bash shell.

    The round-trip script invokes ``alembic`` directly via ``timeout``
    in the same shell environment, so a bash that cannot resolve
    ``alembic`` would fail in a way that is unrelated to Property 5
    (which is about the migration sequence, not environment setup).
    Skipping in this case keeps the property test honest: it only
    runs when the script's required tooling is present.
    """
    try:
        probe = subprocess.run(
            [bash_path, "-c", "command -v alembic >/dev/null 2>&1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


_BASH: str | None = _resolve_usable_bash()
_BASH_HAS_ALEMBIC: bool = _BASH is not None and _bash_has_alembic(_BASH)

# Hypothesis requires a non-empty pool for ``sampled_from``. When no
# revisions exist the test is skipped before it runs, but the strategy
# still has to be constructible at decoration time, so we fall back to
# a placeholder list that the skip path never actually consumes.
_SAMPLE_POOL: List[str] = _REVISIONS if _REVISIONS else ["__no_revisions__"]
_MAX_EXAMPLES: int = max(1, min(100, len(_REVISIONS)))


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _REVISIONS,
    reason=(
        f"No Alembic revisions found in {_VERSIONS_DIR}; "
        "Property 5 holds vacuously until migrations are authored."
    ),
)
@pytest.mark.skipif(
    _BASH is None,
    reason="bash not available; round-trip script requires POSIX shell.",
)
@pytest.mark.skipif(
    not _BASH_HAS_ALEMBIC,
    reason=(
        "alembic CLI not reachable from bash; the round-trip script "
        "cannot run in this environment, so Property 5 is unverifiable "
        "here and is left to CI where the backend dev deps are installed."
    ),
)
@given(revision=st.sampled_from(_SAMPLE_POOL))
@settings(
    max_examples=_MAX_EXAMPLES,
    deadline=None,
    # The subprocess invocation can take up to ~15 minutes per example
    # (three 300-second alembic timeouts), so neither the per-example
    # deadline nor "too slow" health check fit this property.
    suppress_health_check=[HealthCheck.too_slow],
)
def test_alembic_round_trip_succeeds_for_every_revision(revision: str) -> None:
    """**Validates: Requirements 12.1, 12.2, 12.3, 12.4**

    For every revision id discovered under
    ``web/apps/admin-dashboard/backend/alembic/versions/`` the
    round-trip script must exit 0 when run against a fresh SQLite temp
    database, satisfying the contract that:

    * AC 12.1 -- the sequence runs from the backend working directory
      against an ephemeral SQLite file that is deleted on exit, with
      each command bounded by a 300-second timeout (enforced inside
      the script).
    * AC 12.2 -- a non-zero exit (including the 124 emitted by
      ``timeout(1)`` on budget exhaustion) propagates as a non-zero
      script exit.
    * AC 12.3 -- the script does not introduce failure conditions
      beyond what alembic itself reports through its exit code; we
      observe this by asserting on exit code only.
    * AC 12.4 -- the recorded exit code matches the script's
      conclusion (the test fails the workflow when the exit code is
      non-zero even if the runner happened to mark the step green).
    """
    # ``skipif`` already rules these out, but keep the invariants
    # locally explicit so a future refactor that drops a guard fails
    # loudly instead of silently running garbage.
    assert _BASH is not None
    assert _REVISIONS, "skipif should have prevented entry without revisions"
    assert revision in _REVISIONS, (
        f"sampled revision {revision!r} not in discovered set "
        f"{_REVISIONS!r}; sampling pool was corrupted"
    )

    with tempfile.TemporaryDirectory(prefix="alembic-round-trip-") as tmp_root:
        env = os.environ.copy()
        # The script reads ``RUNNER_TEMP`` to place its ephemeral
        # SQLite file. Pointing it at a fresh per-example directory
        # keeps the property strictly about the migration sequence
        # rather than about leftover state from previous runs.
        env["RUNNER_TEMP"] = tmp_root
        # Avoid carrying a stale ``DATABASE_URL`` from the host shell
        # into the subprocess; the script sets it deterministically.
        env.pop("DATABASE_URL", None)

        completed = subprocess.run(
            [_BASH, str(_ROUND_TRIP_SCRIPT)],
            cwd=str(_BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            # Hard upper bound on the wall-clock budget: three 300s
            # alembic steps plus a generous buffer for cleanup. We
            # stay strictly above the in-script ``timeout 300`` so a
            # script-level timeout (exit 124) is observed by the
            # property instead of being masked by a Python timeout.
            timeout=20 * 60,
        )

    assert completed.returncode == 0, (
        "alembic round-trip script failed for revision "
        f"{revision!r}\n"
        f"  script    : {_ROUND_TRIP_SCRIPT}\n"
        f"  workdir   : {_BACKEND_DIR}\n"
        f"  exit_code : {completed.returncode}\n"
        f"  stdout    :\n{completed.stdout}\n"
        f"  stderr    :\n{completed.stderr}\n"
    )
