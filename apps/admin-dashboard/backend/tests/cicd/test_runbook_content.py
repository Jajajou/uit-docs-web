"""Content-check tests for the admin-dashboard runbook.

**Validates: Requirements 13.2, 15.1, 17.4, 18.5, 18.6, 20.8**

This file enforces the structural and substantive contract of
``docs/runbooks/admin-dashboard.md`` so that the runbook stays the
authoritative single source of truth referenced from the spec
(R13.2, R15.1).

The runbook is parsed once (level-2 section headers, ``## <name>``)
into a mapping of section name → section body. Tests then assert:

* every section enumerated by the spec is present (R15.1);
* every secret name enumerated by R13.1 appears in the
  ``Required Secrets`` section as an exact case-sensitive substring
  (R13.2);
* the LangGraph upstream contract surface ``POST /threads``,
  ``POST /threads/{id}/runs``, ``GET /health`` is documented
  (R15.3, captured here via the ``LangGraph Upstream`` section);
* the cosign signing path is documented for both keyless OIDC and
  the ``COSIGN_PRIVATE_KEY`` alternative (R20.8 / design table C1
  ``docker-build-publish``);
* the rollback steps name ``alembic downgrade`` and
  ``/etc/uit-docs/deployment.json`` (R18.5);
* every workflow YAML referenced from the design (the eight files in
  the workflow registry) exists on disk under
  ``.github/workflows/``.

A small property test (Hypothesis) draws random required section
names and asserts the section body is filled in with at least
100 characters of non-whitespace content, so that a future edit
that accidentally empties a section (leaving only the header) is
caught.

Run from ``web/apps/admin-dashboard/backend``::

    pytest tests/cicd/test_runbook_content.py -v
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.cicd.workflow_registry import WORKFLOWS


# ---------------------------------------------------------------------------
# Runbook location
# ---------------------------------------------------------------------------
#
# The runbook lives at ``<repo>/docs/runbooks/admin-dashboard.md``. This
# test file is at ``<repo>/web/apps/admin-dashboard/backend/tests/cicd/
# test_runbook_content.py`` -- six ``parents`` to reach the repo root,
# matching the convention used elsewhere in this test directory.

_REPO_ROOT: Path = Path(__file__).resolve().parents[6]
_RUNBOOK_PATH: Path = _REPO_ROOT / "docs" / "runbooks" / "admin-dashboard.md"

assert _RUNBOOK_PATH.is_file(), (
    f"Runbook missing at expected path: {_RUNBOOK_PATH}. "
    "Task 15.1 must populate docs/runbooks/admin-dashboard.md before "
    "the content-check tests can run."
)


# ---------------------------------------------------------------------------
# Canonical inputs
# ---------------------------------------------------------------------------

#: Level-2 section names the runbook MUST contain (per task 15.1 and the
#: spec sections it cites). Order matches the order they appear in the
#: runbook narrative; the parser does not depend on order so the list
#: doubles as both presence check and the Hypothesis sample space.
_REQUIRED_SECTIONS: tuple[str, ...] = (
    "Required Secrets",
    "LangGraph Upstream",
    "Rollback",
    "On-call",
    "Operator Commands",
    "Production Configuration",
)

#: Canonical secret names from Requirement 13.1 that the runbook's
#: ``Required Secrets`` section MUST list. Match is case-sensitive and
#: substring-based, so a row in the secrets table that quotes the name
#: in backticks (e.g. ``LANGGRAPH_UPSTREAM_URL``) will match.
_REQUIRED_SECRETS: tuple[str, ...] = (
    "LANGGRAPH_UPSTREAM_URL",
    "VERCEL_TOKEN",
    "STAGING_SSH_HOST",
    "STAGING_SSH_USER",
    "SSH_PRIVATE_KEY",
    "PROD_SSH_HOST",
    "PROD_SSH_USER",
    "DEPLOY_FAILURE_WEBHOOK_URL",
)

#: LangGraph upstream contract endpoints (R15.3). The runbook documents
#: each of these in the ``LangGraph Upstream`` section.
_LANGGRAPH_CONTRACT_ENDPOINTS: tuple[str, ...] = (
    "POST",
    "/threads",
    "/threads/{id}/runs",
    "GET",
    "/health",
)


# ---------------------------------------------------------------------------
# Runbook parser
# ---------------------------------------------------------------------------


# A level-2 ATX header in CommonMark: a line starting with exactly two
# ``#`` characters, a single space, then the section title. The runbook
# uses this style consistently; ``setext`` (underline) headers are not
# accepted because the runbook does not use them.
_H2_PATTERN: re.Pattern[str] = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


def _parse_h2_sections(text: str) -> Mapping[str, str]:
    """Return a mapping of level-2 section title → body.

    The body of a section is everything between its ``## <title>`` line
    (exclusive) and the next ``## `` line (exclusive), or end-of-file.
    Higher-level headers (``###`` and below) are kept verbatim inside the
    body of their parent ``##`` section.

    Headers above level 2 (``# Admin Dashboard Runbook``) are ignored;
    their text is treated as preamble before the first ``##`` and is
    dropped.

    The mapping is intentionally a plain ``dict`` so callers can mutate
    it in tests without affecting other tests; sections sharing a title
    (none expected) would collapse, which would itself surface as a
    test failure when the body length check inspects the wrong copy.
    """

    matches = list(_H2_PATTERN.finditer(text))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        title = match.group("title").strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        sections[title] = body
    return sections


# Parse once at module load. The runbook is small (~25 KB) and parsing is
# pure-Python, so caching here keeps every test cheap and avoids
# re-reading the file from disk on each test.
_RUNBOOK_TEXT: str = _RUNBOOK_PATH.read_text(encoding="utf-8")
_SECTIONS: Mapping[str, str] = _parse_h2_sections(_RUNBOOK_TEXT)


# ---------------------------------------------------------------------------
# Section-presence tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("section", _REQUIRED_SECTIONS)
def test_required_section_is_present(section: str) -> None:
    """Each required H2 section name appears as ``## <name>``."""

    assert section in _SECTIONS, (
        f"Runbook is missing required section '## {section}'. "
        f"Found sections: {sorted(_SECTIONS)}."
    )


def test_no_unexpected_section_collisions() -> None:
    """Every required section maps to a non-empty body.

    A repeated ``## <name>`` would collapse in the parser's dict and
    leave one body discarded; an empty body usually indicates the
    section was deleted but its header was kept by accident. Either
    way, the runbook fails its R15.1 contract.
    """

    for section in _REQUIRED_SECTIONS:
        body = _SECTIONS.get(section, "")
        assert body, f"Section '## {section}' has an empty body."


# ---------------------------------------------------------------------------
# Required Secrets content (R13.1, R13.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("secret_name", _REQUIRED_SECRETS)
def test_required_secret_appears_in_required_secrets_section(secret_name: str) -> None:
    """Every R13.1 secret name appears in the ``Required Secrets`` body.

    The check is case-sensitive and substring-based: the runbook may
    quote the secret in backticks or include it inside a Markdown table
    cell, both of which contain the literal name as a substring.
    """

    body = _SECTIONS["Required Secrets"]
    assert secret_name in body, (
        f"Secret '{secret_name}' (Requirement 13.1) is missing from the "
        f"'## Required Secrets' section of the runbook."
    )


def test_required_secrets_section_documents_rotation_cadence() -> None:
    """R13.2 demands a rotation cadence ≤ 90 days; the runbook records it.

    Asserting the literal phrase ``90 days`` is sufficient -- the
    runbook uses it consistently in every secret row and in the
    section preamble.
    """

    body = _SECTIONS["Required Secrets"]
    assert "90 days" in body, (
        "Required Secrets section must document a rotation cadence of "
        "at most 90 days (Requirement 13.2)."
    )


# ---------------------------------------------------------------------------
# LangGraph Upstream contract (R15.3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", _LANGGRAPH_CONTRACT_ENDPOINTS)
def test_langgraph_upstream_documents_contract_endpoint(token: str) -> None:
    """The LangGraph contract surface is named in the runbook.

    Each token (HTTP verb or path) is required as a substring inside
    the ``LangGraph Upstream`` section. Splitting the assertion per
    token gives precise failure messages when the runbook drifts.
    """

    body = _SECTIONS["LangGraph Upstream"]
    assert token in body, (
        f"LangGraph Upstream section is missing contract token '{token}'."
    )


def test_langgraph_upstream_documents_secret_only_swap() -> None:
    """R15.2: swapping the upstream is a secret-only change.

    The runbook explicitly calls out that the swap is a secret-only
    change. Asserting the canonical phrase keeps the contract anchored
    to the spec wording rather than to a paraphrase.
    """

    body = _SECTIONS["LangGraph Upstream"]
    assert "secret-only" in body, (
        "LangGraph Upstream section must describe the upstream swap as a "
        "'secret-only' change (Requirement 15.2)."
    )


# ---------------------------------------------------------------------------
# Rollback content (R18.5, R12.6/R12.8)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "alembic downgrade",
        "/etc/uit-docs/deployment.json",
    ],
)
def test_rollback_section_mentions_required_phrase(phrase: str) -> None:
    """The Rollback section references the alembic and deployment-record steps."""

    body = _SECTIONS["Rollback"]
    assert phrase in body, (
        f"Rollback section is missing required phrase '{phrase}'."
    )


# ---------------------------------------------------------------------------
# Cosign signing (design C1 docker-build-publish, R7.6/R7.7)
# ---------------------------------------------------------------------------


def test_runbook_documents_cosign_keyless_oidc() -> None:
    """The runbook describes the default keyless OIDC signing path.

    Both ``keyless`` and ``OIDC`` must appear together in the runbook
    so that a reader landing in the cosign section sees that the
    default uses Sigstore-issued short-lived certificates and not a
    long-lived signing key.
    """

    text = _RUNBOOK_TEXT
    assert "keyless" in text, "Runbook must document cosign keyless signing."
    assert "OIDC" in text, "Runbook must document the OIDC token used for keyless signing."


def test_runbook_documents_cosign_private_key_alternative() -> None:
    """The runbook documents the ``COSIGN_PRIVATE_KEY`` alternative path."""

    text = _RUNBOOK_TEXT
    assert "COSIGN_PRIVATE_KEY" in text, (
        "Runbook must document the COSIGN_PRIVATE_KEY alternative for "
        "key-based cosign signing when keyless OIDC is unavailable."
    )


# ---------------------------------------------------------------------------
# Workflow-file existence (design table C1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "workflow_file_path",
    [wf.file_path for wf in WORKFLOWS],
    ids=[wf.name for wf in WORKFLOWS],
)
def test_workflow_file_referenced_in_design_exists(workflow_file_path: str) -> None:
    """Every workflow YAML named in the design exists on disk.

    The runbook references several workflow files by name
    (``staging-deploy.yml``, ``production-deploy.yml``,
    ``docker-build-publish.yml``, etc.); the registry mirrors design
    table C1. If the file is renamed or deleted, the runbook
    cross-references rot silently -- this test prevents that.
    """

    target = _REPO_ROOT / workflow_file_path
    assert target.is_file(), (
        f"Workflow file '{workflow_file_path}' referenced in design is "
        f"missing on disk at {target}."
    )


# ---------------------------------------------------------------------------
# Property test: required sections are non-stub
# ---------------------------------------------------------------------------
#
# **Validates: Requirements 13.2, 15.1, 17.4, 18.5, 18.6, 20.8**
#
# Property: for every required section name ``s``, the runbook body
# under ``## s`` contains at least 100 characters of non-whitespace
# content. The 100-character threshold is a deliberately low bar that
# catches the failure mode of a header being kept while its content is
# accidentally deleted (or never filled in), without locking the
# runbook to a specific verbosity. Hypothesis draws ``s`` uniformly
# from ``_REQUIRED_SECTIONS``.


@settings(max_examples=50, deadline=None)
@given(section=st.sampled_from(_REQUIRED_SECTIONS))
def test_required_section_body_is_filled_in(section: str) -> None:
    """Random required section has ≥100 non-whitespace characters."""

    body = _SECTIONS[section]
    non_whitespace = re.sub(r"\s+", "", body)
    assert len(non_whitespace) >= 100, (
        f"Section '## {section}' has only {len(non_whitespace)} "
        "non-whitespace characters; expected at least 100. The section "
        "appears to be a stub or was accidentally emptied."
    )
