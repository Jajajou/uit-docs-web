"""Property-based test for the backend coverage gate.

Property 13: Coverage Gate.

**Validates: Requirements 3.6**

For every Cobertura ``coverage.xml`` whose root ``line-rate`` attribute is
some value ``r in [0.0, 1.0]``, invoking ``scripts/ci/coverage_gate.py``
must exit with status 0 iff ``r >= THRESHOLD`` (with ``THRESHOLD = 0.70``
per ``coverage_gate.py``), and exit with status 1 otherwise.

Strategy:

* Hypothesis draws floats in ``[0.0, 1.0]`` (no NaN/inf) and always
  exercises the explicit edge values ``0.6999``, ``0.70`` and ``0.7001``
  via ``@example`` so the boundary on the threshold is hit on every run.
* For each draw we materialise a minimal Cobertura XML
  (``<coverage line-rate="...">``) in a temporary directory, invoke the
  script via ``subprocess.run`` against the host's Python interpreter and
  assert the exit code matches the spec.
* ``max_examples=100`` per the task description.

The script under test is located at the repository root and the test
lives at::

    web/apps/admin-dashboard/backend/tests/cicd/test_coverage_gate.py

So ``parents[6]`` of this file is the repo root. We resolve the path
once at import time and assert that the script exists -- a missing
script would mean task 3.5 was reverted and is a different problem from
the property under test.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from hypothesis import example, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Locate the script under test
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[6]
_SCRIPT_PATH: Path = _REPO_ROOT / "scripts" / "ci" / "coverage_gate.py"

assert _SCRIPT_PATH.is_file(), (
    f"coverage_gate.py not found at expected path {_SCRIPT_PATH}; "
    "task 3.5 must produce this script before task 3.6 can validate it"
)


def _load_threshold() -> float:
    """Import ``THRESHOLD`` from the script under test.

    The script lives outside any package, so we load it via
    ``importlib.util`` rather than a normal ``import``. Failing here
    means the script has been refactored in a way the property test
    needs to know about, so we want a hard import error rather than a
    silent fallback to ``0.70``.
    """
    spec = importlib.util.spec_from_file_location(
        "_coverage_gate_under_test", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return float(module.THRESHOLD)


THRESHOLD: float = _load_threshold()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_coverage_xml(directory: Path, line_rate: float) -> Path:
    """Write a minimal Cobertura ``coverage.xml`` and return its path.

    The script only reads the root ``line-rate`` attribute, so the
    document is intentionally minimal -- adding more nodes would just
    create surface area for unrelated XML quirks to leak into the test.
    """
    # ``repr`` keeps full precision (e.g. 0.6999 stays 0.6999) which is
    # important because the script compares to ``THRESHOLD`` exactly.
    xml = (
        '<?xml version="1.0" ?>\n'
        f'<coverage line-rate="{line_rate!r}" version="6.0" '
        'timestamp="0">\n'
        "  <packages/>\n"
        "</coverage>\n"
    )
    path = directory / "coverage.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def _invoke_gate(coverage_xml: Path) -> int:
    """Run the script against ``coverage_xml`` and return its exit code."""
    completed = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), str(coverage_xml)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


@given(
    line_rate=st.floats(
        min_value=0.0,
        max_value=1.0,
        allow_nan=False,
        allow_infinity=False,
    )
)
@example(line_rate=0.6999)
@example(line_rate=0.70)
@example(line_rate=0.7001)
@example(line_rate=0.0)
@example(line_rate=1.0)
@settings(max_examples=100, deadline=None)
def test_coverage_gate_threshold(line_rate: float) -> None:
    """**Validates: Requirements 3.6**

    Exit code 0 iff observed ``line-rate >= THRESHOLD`` (0.70); exit
    code 1 otherwise.
    """
    with tempfile.TemporaryDirectory(prefix="coverage_gate_") as raw_dir:
        workdir = Path(raw_dir)
        coverage_xml = _write_coverage_xml(workdir, line_rate)
        rc = _invoke_gate(coverage_xml)

    expected = 0 if line_rate >= THRESHOLD else 1
    assert rc == expected, (
        "coverage_gate exit code disagrees with the THRESHOLD contract.\n"
        f"  line_rate = {line_rate!r}\n"
        f"  THRESHOLD = {THRESHOLD!r}\n"
        f"  expected_rc = {expected}\n"
        f"  actual_rc = {rc}"
    )
