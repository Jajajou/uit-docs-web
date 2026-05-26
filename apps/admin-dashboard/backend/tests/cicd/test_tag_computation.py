"""Property-based test for the GHCR tag computation script.

Property 12: Tag Computation.

**Validates: Requirements 7.1, 7.2, 7.4**

For any trigger event ``e`` of type ``push:main`` or ``push:tag`` with
associated ``ref`` and ``sha``, the set of GHCR image tag suffixes
produced by ``scripts/ci/compute_tags.sh`` SHALL equal:

* ``{"main", "sha-" + sha}`` when ``e`` is ``push:main``;
* ``{ref_name, "latest"}`` when ``e`` is ``push:tag`` and
  ``ref_name`` matches ``v*``;
* the empty set when ``e`` is ``push:tag`` and ``ref_name`` does not
  match ``v*`` (the publish contract is undefined for non-``v*`` tags;
  the script encodes this as silent empty output, exit 0).

Strategy:

* Hypothesis draws an ``event_kind`` from ``{"push:main", "push:tag"}``.
* For ``push:main`` it draws a 40-hex commit SHA (lowercase,
  ``[0-9a-f]{40}``).
* For ``push:tag`` it draws either a ``v``-prefixed ref (matching
  ``v*``) or a non-``v`` prefixed ref (e.g. ``release-1.2.3``,
  ``hotfix/foo``).
* The script is invoked via ``subprocess.run`` against a discovered
  bash interpreter (with a Windows/WSL-aware fallback). Stdout is
  parsed by stripping blank lines and converting to a set; exit code
  is asserted to be 0 in every well-formed case.
* ``max_examples=100``.

The script under test is at the repository root and the test lives at::

    web/apps/admin-dashboard/backend/tests/cicd/test_tag_computation.py

so ``parents[6]`` of this file is the repository root.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Locate the script under test
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[6]
_SCRIPT_PATH: Path = _REPO_ROOT / "scripts" / "ci" / "compute_tags.sh"

assert _SCRIPT_PATH.is_file(), (
    f"compute_tags.sh not found at expected path {_SCRIPT_PATH}; "
    "task 6.6 must produce this script before task 6.7 can validate it"
)


# ---------------------------------------------------------------------------
# Bash discovery (mirrors tests/scripts/test_smoke_test.py)
# ---------------------------------------------------------------------------


def _resolve_usable_bash() -> str | None:
    """Return the path to a bash interpreter that actually works.

    On Windows, ``shutil.which("bash")`` may resolve to the WSL stub at
    ``C:\\Windows\\System32\\bash.exe`` which only succeeds when a Linux
    distribution has been installed. Probe each candidate with a trivial
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


_BASH: str | None = _resolve_usable_bash()


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------


# 40-hex lowercase SHA: matches the format produced by `${{ github.sha }}`.
_sha_strategy = st.from_regex(r"\A[0-9a-f]{40}\Z", fullmatch=True)


# v-prefixed tag refs. The ref_name passed to the script is the bare ref
# (e.g. "v1.2.3"), not the full ``refs/tags/v1.2.3`` form. Allow common
# semver-ish characters but keep the prefix constraint.
_v_tag_strategy = st.from_regex(
    r"\Av[0-9A-Za-z][0-9A-Za-z._-]{0,30}\Z", fullmatch=True
)


# Non-v prefixed tag refs (anything whose first character is not
# lowercase ``v``). Excludes empty strings and shell-meaningful chars
# that could perturb the test harness rather than the script's logic.
_non_v_tag_strategy = st.from_regex(
    r"\A[0-9A-Za-uw-z][0-9A-Za-z._/-]{0,30}\Z", fullmatch=True
).filter(lambda s: not s.startswith("v"))


def _push_main_examples() -> st.SearchStrategy[Tuple[str, str]]:
    return _sha_strategy.map(lambda sha: ("push:main", sha))


def _push_tag_v_examples() -> st.SearchStrategy[Tuple[str, str]]:
    return _v_tag_strategy.map(lambda ref: ("push:tag", ref))


def _push_tag_non_v_examples() -> st.SearchStrategy[Tuple[str, str]]:
    return _non_v_tag_strategy.map(lambda ref: ("push:tag", ref))


_event_strategy = st.one_of(
    _push_main_examples(),
    _push_tag_v_examples(),
    _push_tag_non_v_examples(),
)


# ---------------------------------------------------------------------------
# Reference oracle and helpers
# ---------------------------------------------------------------------------


def _expected_tag_set(event_kind: str, ref_or_sha: str) -> set[str]:
    """Compute the expected tag-suffix set per Property 12."""
    if event_kind == "push:main":
        return {"main", f"sha-{ref_or_sha}"}
    if event_kind == "push:tag":
        if ref_or_sha.startswith("v"):
            return {ref_or_sha, "latest"}
        return set()
    raise AssertionError(f"unsupported event_kind in oracle: {event_kind!r}")


def _invoke_compute_tags(event_kind: str, ref_or_sha: str) -> subprocess.CompletedProcess[str]:
    assert _BASH is not None  # guarded by skipif at the test level
    return subprocess.run(
        [_BASH, str(_SCRIPT_PATH), event_kind, ref_or_sha],
        capture_output=True,
        text=True,
        timeout=15,
    )


def _parse_tag_set(stdout: str) -> set[str]:
    """Parse one-tag-per-line stdout into a set, dropping blank lines."""
    return {line for line in (raw.strip() for raw in stdout.splitlines()) if line}


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_BASH is None, reason="bash unavailable")
@given(event=_event_strategy)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_compute_tags_property_12(event: Tuple[str, str]) -> None:
    """**Validates: Requirements 7.1, 7.2, 7.4**

    The tag set printed by ``compute_tags.sh`` matches Property 12:

    * ``push:main`` with SHA ``s`` → ``{"main", "sha-" + s}``;
    * ``push:tag`` with ref ``r`` matching ``v*`` → ``{r, "latest"}``;
    * ``push:tag`` with ref not matching ``v*`` → ``∅`` (and exit 0,
      silent stdout).
    """
    event_kind, ref_or_sha = event

    result = _invoke_compute_tags(event_kind, ref_or_sha)

    assert result.returncode == 0, (
        "compute_tags.sh exited non-zero for a well-formed event.\n"
        f"  event_kind = {event_kind!r}\n"
        f"  ref_or_sha = {ref_or_sha!r}\n"
        f"  exit_code  = {result.returncode}\n"
        f"  stdout     = {result.stdout!r}\n"
        f"  stderr     = {result.stderr!r}"
    )

    actual = _parse_tag_set(result.stdout)
    expected = _expected_tag_set(event_kind, ref_or_sha)

    assert actual == expected, (
        "compute_tags.sh tag set disagrees with Property 12.\n"
        f"  event_kind = {event_kind!r}\n"
        f"  ref_or_sha = {ref_or_sha!r}\n"
        f"  expected   = {expected!r}\n"
        f"  actual     = {actual!r}\n"
        f"  stdout     = {result.stdout!r}"
    )

    # Extra guard: non-v* push:tag refs MUST produce empty stdout (the
    # task description calls this out explicitly). The set comparison
    # above already covers this, but we surface a clearer failure here
    # if the script ever decides to emit comments or whitespace lines
    # that happen to parse to an empty set.
    if event_kind == "push:tag" and not ref_or_sha.startswith("v"):
        assert result.stdout.strip() == "", (
            "push:tag with non-v* ref must produce no tag output.\n"
            f"  ref_or_sha = {ref_or_sha!r}\n"
            f"  stdout     = {result.stdout!r}"
        )
