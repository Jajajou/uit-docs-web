"""Cross-validation between the in-code workflow registry and the YAML files.

This is task 16.2 of the ``cicd-deploy-admin-dashboard`` spec. It is a regular
``pytest`` test (not a property test) because the workflow set is finite and
fixed at eight entries (design table C1).

The registry at :mod:`tests.cicd.workflow_registry` is the single source of
truth used by the path-filter model in :mod:`tests.cicd.workflow_model`. The
authored ``.github/workflows/*.yml`` files are what GitHub Actions actually
executes. If those two drift -- for example, a workflow's ``paths:`` filter
is widened in YAML without the registry being updated -- the property test
in ``test_path_filter.py`` would silently certify the wrong contract.

This module locks the two together. For every entry in
:data:`tests.cicd.workflow_registry.WORKFLOWS` we:

1. Open the corresponding ``.github/workflows/<name>.yml`` and parse it
   with PyYAML.
2. Translate the ``on:`` block into the same trigger encoding used by the
   registry (``"push:main"``, ``"push:tag:v*"``, ``"schedule:<cron>"``,
   ``"workflow_run:<workflow>:<branch>"``, etc.) and assert equality with
   ``Workflow.triggers``.
3. For path-filtered workflows (``frontend-ci``, ``backend-ci``,
   ``langgraph-ci``) assert that ``on.pull_request.paths`` and
   ``on.push.paths`` each equal the registry's ``path_filter``.
4. Assert ``concurrency.group`` matches
   :data:`tests.cicd.workflow_registry.CONCURRENCY_GROUPS`.

A YAML quirk worth noting: PyYAML's ``safe_load`` parses the bare key
``on:`` as the boolean ``True`` because YAML 1.1 considers ``on`` a truthy
literal. We compensate by reading both ``"on"`` and ``True`` from the
parsed mapping; a workflow that uses neither is malformed and the test
fails with a clear message.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 5.4.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from tests.cicd.workflow_model import Workflow
from tests.cicd.workflow_registry import (
    CONCURRENCY_GROUPS,
    WORKFLOWS,
)


# ---------------------------------------------------------------------------
# Path resolution
#
# This test file lives at:
#     web/apps/admin-dashboard/backend/tests/cicd/test_workflow_registry_consistency.py
# Six ``parents`` walk-ups land at the repository root, matching the
# convention used by sibling tests (``test_coverage_gate.py``,
# ``test_tag_computation.py``, ``test_runbook_content.py``).
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[6]
_WORKFLOWS_DIR: Path = _REPO_ROOT / ".github" / "workflows"

# Path-filtered workflows per design table C1 / Requirements 1.2-1.4. These
# are the only registry entries whose ``path_filter`` is non-empty, but we
# encode the set explicitly here so the test fails loudly if a future entry
# is added with a non-empty ``path_filter`` and no matching YAML assertion.
_PATH_FILTERED_WORKFLOWS: frozenset[str] = frozenset(
    {"frontend-ci", "backend-ci", "langgraph-ci"}
)


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _load_workflow_yaml(file_path: Path) -> Mapping[str, Any]:
    """Parse a workflow YAML and normalise the YAML 1.1 ``on``-as-True quirk.

    PyYAML's ``safe_load`` resolves the bare key ``on:`` as the boolean
    ``True`` because YAML 1.1's type schema treats ``on`` as a truthy
    literal. GitHub Actions itself reads the YAML 1.2 spelling, so we
    accept either key and re-key it under the canonical string ``"on"``
    so the rest of the test can address it consistently.
    """
    with file_path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    assert isinstance(loaded, Mapping), (
        f"{file_path} did not parse as a YAML mapping"
    )
    parsed = dict(loaded)
    if "on" not in parsed and True in parsed:
        parsed["on"] = parsed.pop(True)
    assert "on" in parsed, (
        f"{file_path} has no `on:` block (or it was not recognised by "
        f"PyYAML); keys were {list(parsed.keys())!r}"
    )
    return parsed


def _encode_triggers(on_block: Mapping[Any, Any]) -> set[str]:
    """Translate a workflow's ``on:`` block into the registry's trigger set.

    The encoding mirrors the convention documented on
    :class:`tests.cicd.workflow_model.Workflow`:

    * ``pull_request:`` -> ``"pull_request"``
    * ``workflow_dispatch:`` -> ``"workflow_dispatch"``
    * ``push: branches: [<b>...]`` -> ``"push:<b>"`` per branch
    * ``push: tags: [<g>...]`` -> ``"push:tag:<g>"`` per tag glob
    * ``schedule: [{cron: <c>}, ...]`` -> ``"schedule:<c>"`` per cron
    * ``workflow_run: workflows: [<w>...] branches: [<b>...]`` ->
      ``"workflow_run:<w>:<b>"`` for the cartesian product

    Any unknown event kind raises ``AssertionError`` so a future YAML
    addition forces a deliberate update to both the registry and this
    encoder, instead of silently bypassing the consistency check.
    """
    encoded: set[str] = set()
    for raw_kind, body in on_block.items():
        # YAML 1.1 may again parse ``on:`` keys ``on``/``off``/``yes``/``no``
        # as booleans; coerce to the canonical string for the dispatch.
        kind = "on" if raw_kind is True else str(raw_kind)

        if kind == "pull_request":
            encoded.add("pull_request")
            continue

        if kind == "workflow_dispatch":
            encoded.add("workflow_dispatch")
            continue

        if kind == "push":
            body = body or {}
            assert isinstance(body, Mapping), (
                f"`on.push` must be a mapping or null, got {type(body).__name__}"
            )
            for branch in body.get("branches") or []:
                encoded.add(f"push:{branch}")
            for tag in body.get("tags") or []:
                encoded.add(f"push:tag:{tag}")
            continue

        if kind == "schedule":
            assert isinstance(body, list), (
                f"`on.schedule` must be a list, got {type(body).__name__}"
            )
            for entry in body:
                assert isinstance(entry, Mapping) and "cron" in entry, (
                    f"`on.schedule` entries must be mappings with a `cron` "
                    f"field, got {entry!r}"
                )
                encoded.add(f"schedule:{entry['cron']}")
            continue

        if kind == "workflow_run":
            body = body or {}
            assert isinstance(body, Mapping), (
                f"`on.workflow_run` must be a mapping, got "
                f"{type(body).__name__}"
            )
            workflows = body.get("workflows") or []
            # Default to a single empty-branch entry so the encoding
            # remains stable when a workflow_run trigger does not declare
            # a branch filter.
            branches = body.get("branches") or [""]
            for wf in workflows:
                for branch in branches:
                    encoded.add(f"workflow_run:{wf}:{branch}")
            continue

        raise AssertionError(
            f"Unrecognised `on:` event kind {kind!r}; update the encoder "
            f"and the registry together"
        )

    return encoded


def _normalise_path_list(value: Any) -> tuple[set[str], list[str]]:
    """Return ``(set, list)`` views of an ``on.<event>.paths`` value.

    The set view is what the equality assertion compares against the
    registry; the list view is included in the assertion message so a
    drift surfaces with the original ordering preserved.
    """
    if value is None:
        return set(), []
    assert isinstance(value, list), (
        f"`paths:` must be a list, got {type(value).__name__}"
    )
    return set(value), list(value)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "workflow",
    WORKFLOWS,
    ids=[wf.name for wf in WORKFLOWS],
)
def test_workflow_file_exists(workflow: Workflow) -> None:
    """Each registered workflow must have a corresponding YAML file."""
    expected_path = _REPO_ROOT / workflow.file_path
    assert expected_path.is_file(), (
        f"Workflow {workflow.name!r} declares file_path={workflow.file_path!r} "
        f"but {expected_path} does not exist"
    )


@pytest.mark.parametrize(
    "workflow",
    WORKFLOWS,
    ids=[wf.name for wf in WORKFLOWS],
)
def test_workflow_triggers_match_registry(workflow: Workflow) -> None:
    """The YAML ``on:`` block encodes to exactly the registry's triggers.

    Validates Requirements 1.1, 1.5-1.8: the trigger set in the registry
    is the contract the path-filter property test certifies, so the YAML
    must agree byte-for-byte (modulo the stable encoding above).
    """
    parsed = _load_workflow_yaml(_REPO_ROOT / workflow.file_path)
    encoded = _encode_triggers(parsed["on"])
    expected = set(workflow.triggers)
    assert encoded == expected, (
        f"Trigger drift in {workflow.file_path}:\n"
        f"  registry    = {sorted(expected)!r}\n"
        f"  yaml encode = {sorted(encoded)!r}\n"
        f"  missing in yaml      = {sorted(expected - encoded)!r}\n"
        f"  extra in yaml        = {sorted(encoded - expected)!r}"
    )


@pytest.mark.parametrize(
    "workflow",
    [wf for wf in WORKFLOWS if wf.name in _PATH_FILTERED_WORKFLOWS],
    ids=lambda wf: wf.name,
)
def test_path_filtered_workflow_paths_match_registry(workflow: Workflow) -> None:
    """``on.pull_request.paths`` and ``on.push.paths`` mirror the registry.

    Validates Requirements 1.2-1.4: a path-filtered workflow's YAML
    ``paths:`` list under both ``pull_request`` and ``push`` must equal
    the registry's ``path_filter`` (set equality, ordering is not
    semantically meaningful in GitHub Actions ``paths:`` matching).
    """
    parsed = _load_workflow_yaml(_REPO_ROOT / workflow.file_path)
    on_block: Mapping[str, Any] = parsed["on"]
    expected = set(workflow.path_filter)
    assert expected, (
        f"Workflow {workflow.name!r} is marked path-filtered but its "
        f"registry path_filter is empty; update the registry or the "
        f"_PATH_FILTERED_WORKFLOWS set"
    )

    # pull_request branch
    pr_block = on_block.get("pull_request") or {}
    assert isinstance(pr_block, Mapping), (
        f"`on.pull_request` must be a mapping in {workflow.file_path}, "
        f"got {type(pr_block).__name__}"
    )
    pr_paths_set, pr_paths_list = _normalise_path_list(pr_block.get("paths"))
    assert pr_paths_set == expected, (
        f"`on.pull_request.paths` drift in {workflow.file_path}:\n"
        f"  registry path_filter = {sorted(expected)!r}\n"
        f"  yaml pr paths        = {pr_paths_list!r}"
    )

    # push branch
    push_block = on_block.get("push") or {}
    assert isinstance(push_block, Mapping), (
        f"`on.push` must be a mapping in {workflow.file_path}, "
        f"got {type(push_block).__name__}"
    )
    push_paths_set, push_paths_list = _normalise_path_list(
        push_block.get("paths")
    )
    assert push_paths_set == expected, (
        f"`on.push.paths` drift in {workflow.file_path}:\n"
        f"  registry path_filter = {sorted(expected)!r}\n"
        f"  yaml push paths      = {push_paths_list!r}"
    )


@pytest.mark.parametrize(
    "workflow",
    WORKFLOWS,
    ids=[wf.name for wf in WORKFLOWS],
)
def test_concurrency_group_matches_registry(workflow: Workflow) -> None:
    """``concurrency.group`` matches :data:`CONCURRENCY_GROUPS`.

    Validates Requirement 5.4: every workflow declares the documented
    concurrency group so concurrent in-flight runs collapse to the most
    recent one (``cancel-in-progress: true`` for CI gates, ``false`` for
    deploy gates).
    """
    parsed = _load_workflow_yaml(_REPO_ROOT / workflow.file_path)
    concurrency = parsed.get("concurrency")
    assert isinstance(concurrency, Mapping), (
        f"{workflow.file_path} must declare a `concurrency:` mapping; "
        f"got {type(concurrency).__name__}"
    )
    actual_group = concurrency.get("group")
    expected_group = CONCURRENCY_GROUPS[workflow.name]
    assert actual_group == expected_group, (
        f"`concurrency.group` drift in {workflow.file_path}:\n"
        f"  registry = {expected_group!r}\n"
        f"  yaml     = {actual_group!r}"
    )


def test_path_filtered_set_matches_registry_metadata() -> None:
    """The hard-coded path-filtered set agrees with the registry.

    A registry entry with a non-empty ``path_filter`` MUST be in
    :data:`_PATH_FILTERED_WORKFLOWS`, and vice versa. This guards against
    a future workflow being added to the registry with a path filter but
    being silently excluded from the path-filter assertions above.
    """
    registry_with_paths = {wf.name for wf in WORKFLOWS if wf.path_filter}
    assert registry_with_paths == _PATH_FILTERED_WORKFLOWS, (
        f"Path-filtered set drift:\n"
        f"  _PATH_FILTERED_WORKFLOWS = {sorted(_PATH_FILTERED_WORKFLOWS)!r}\n"
        f"  registry (path_filter)   = {sorted(registry_with_paths)!r}\n"
    )
