#!/usr/bin/env python3
"""Backend coverage gate.

Parses a Cobertura-style ``coverage.xml`` (as produced by
``pytest --cov=app --cov-report=xml``) and enforces a minimum
line-rate. Exits 0 when the root ``line-rate`` attribute is at least
``THRESHOLD``; exits 1 otherwise with an explanatory message on stderr.

The threshold is exposed as the module-level constant ``THRESHOLD`` so
property tests (see task 3.6, ``tests/cicd/test_coverage_gate.py``) can
import the exact value the script enforces.

Usage:
    python scripts/ci/coverage_gate.py [path/to/coverage.xml]

If no path is supplied, ``coverage.xml`` in the current working
directory is used.

Validates: Requirements 3.6
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Module-level constant so the property test in task 3.6 can reference
# the exact threshold the script enforces. Do not hardcode 0.70 in
# multiple places.
THRESHOLD: float = 0.70


def _fail(message: str) -> int:
    """Print ``message`` to stderr and return exit code 1."""
    print(message, file=sys.stderr)
    return 1


def evaluate(coverage_xml_path: Path) -> int:
    """Return process exit code for the given ``coverage.xml`` path.

    Exit codes:
        0 — file parsed and root ``line-rate`` is >= ``THRESHOLD``.
        1 — file missing, malformed, attribute missing/non-numeric, or
            line-rate below the threshold.
    """
    if not coverage_xml_path.exists():
        return _fail(
            f"coverage_gate: coverage report not found at {coverage_xml_path}; "
            f"expected pytest --cov-report=xml to produce it"
        )

    try:
        tree = ET.parse(coverage_xml_path)
    except ET.ParseError as exc:
        return _fail(
            f"coverage_gate: failed to parse {coverage_xml_path}: {exc}"
        )

    root = tree.getroot()
    raw = root.get("line-rate")
    if raw is None:
        return _fail(
            f"coverage_gate: {coverage_xml_path} root element <{root.tag}> "
            f"has no 'line-rate' attribute; is this a Cobertura coverage report?"
        )

    try:
        line_rate = float(raw)
    except ValueError:
        return _fail(
            f"coverage_gate: {coverage_xml_path} 'line-rate' attribute "
            f"is not a number (got {raw!r})"
        )

    if line_rate >= THRESHOLD:
        # Brief OK line so CI logs show the observed value.
        print(
            f"coverage_gate: OK line-rate={line_rate:.4f} "
            f">= threshold={THRESHOLD:.2f} ({coverage_xml_path})"
        )
        return 0

    return _fail(
        f"coverage_gate: FAIL line-rate={line_rate:.4f} "
        f"< threshold={THRESHOLD:.2f} ({coverage_xml_path})"
    )


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        return _fail(
            "coverage_gate: usage: coverage_gate.py [path/to/coverage.xml]"
        )
    path = Path(argv[1]) if len(argv) == 2 else Path("coverage.xml")
    return evaluate(path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
