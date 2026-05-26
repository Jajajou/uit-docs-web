"""Canonical registry of the eight CI/CD workflows for this repository.

This module is the single source of truth that keeps the GitHub Actions YAML
files under ``.github/workflows/`` synchronized with the path-filter model
defined in ``tests/cicd/workflow_model.py`` (data model D2).

Every entry in :data:`WORKFLOWS` MUST mirror, byte-for-byte, the corresponding
``name``, ``file_path``, trigger set, and path filters in design document
table C1. Concurrency group templates from the same table are exposed via
:data:`CONCURRENCY_GROUPS` so tests can assert that each workflow YAML uses
the documented concurrency key.

Trigger string conventions (matching :func:`workflow_model.matches`):

* ``"pull_request"`` -- ``on: pull_request`` against any base branch.
* ``"push:main"`` -- push to the ``main`` branch.
* ``"push:tag:v*"`` -- push of a tag whose name matches the glob ``v*``.
* ``"workflow_dispatch"`` -- manual run via the Actions UI / API.
* ``"schedule:<cron>"`` -- scheduled run with the given cron expression.
* ``"workflow_run:<workflow>:<branch>"`` -- chained run when ``<workflow>``
  completes successfully on ``<branch>``.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

from typing import Mapping

from tests.cicd.workflow_model import Workflow

__all__ = ["WORKFLOWS", "CONCURRENCY_GROUPS", "WORKFLOWS_BY_NAME"]


# ---------------------------------------------------------------------------
# Quality-gate workflows (R1.1, R1.2-R1.4)
# ---------------------------------------------------------------------------

_FRONTEND_CI = Workflow(
    name="frontend-ci",
    file_path=".github/workflows/frontend-ci.yml",
    triggers=frozenset({"pull_request", "push:main"}),
    path_filter=(
        "web/apps/admin-dashboard/frontend/**",
        ".github/workflows/frontend-ci.yml",
    ),
)

_BACKEND_CI = Workflow(
    name="backend-ci",
    file_path=".github/workflows/backend-ci.yml",
    triggers=frozenset({"pull_request", "push:main"}),
    path_filter=(
        "web/apps/admin-dashboard/backend/**",
        ".github/workflows/backend-ci.yml",
    ),
)

_LANGGRAPH_CI = Workflow(
    name="langgraph-ci",
    file_path=".github/workflows/langgraph-ci.yml",
    triggers=frozenset({"pull_request", "push:main"}),
    path_filter=(
        "LangGraph/**",
        ".github/workflows/langgraph-ci.yml",
    ),
)

# ---------------------------------------------------------------------------
# Always-on / scheduled workflows (R1.8)
#
# These workflows do not declare a `paths:` filter; per the model contract,
# an empty ``path_filter`` causes :func:`matches` to return ``True`` for any
# event whose trigger key is in ``triggers``.
# ---------------------------------------------------------------------------

_E2E_LIVE = Workflow(
    name="e2e-live",
    file_path=".github/workflows/e2e-live.yml",
    triggers=frozenset({"schedule:0 18 * * *", "workflow_dispatch"}),
    path_filter=(),
)

_DOCKER_BUILD_PUBLISH = Workflow(
    name="docker-build-publish",
    file_path=".github/workflows/docker-build-publish.yml",
    triggers=frozenset({"push:main", "push:tag:v*"}),
    path_filter=(),
)

_RELEASE = Workflow(
    name="release",
    file_path=".github/workflows/release.yml",
    triggers=frozenset({"push:tag:v*"}),
    path_filter=(),
)

_STAGING_DEPLOY = Workflow(
    name="staging-deploy",
    file_path=".github/workflows/staging-deploy.yml",
    triggers=frozenset({"workflow_run:docker-build-publish:main"}),
    path_filter=(),
)

_PRODUCTION_DEPLOY = Workflow(
    name="production-deploy",
    file_path=".github/workflows/production-deploy.yml",
    triggers=frozenset({"push:tag:v*", "workflow_dispatch"}),
    path_filter=(),
)


WORKFLOWS: tuple[Workflow, ...] = (
    _FRONTEND_CI,
    _BACKEND_CI,
    _LANGGRAPH_CI,
    _E2E_LIVE,
    _DOCKER_BUILD_PUBLISH,
    _RELEASE,
    _STAGING_DEPLOY,
    _PRODUCTION_DEPLOY,
)

#: Lookup-by-name view over :data:`WORKFLOWS` for tests that index workflows
#: by their declared ``name``.
WORKFLOWS_BY_NAME: Mapping[str, Workflow] = {wf.name: wf for wf in WORKFLOWS}

#: Concurrency group templates per design table C1. The literal ``${{ ... }}``
#: GitHub Actions expression is preserved so tests can string-compare against
#: the rendered ``concurrency.group`` field in each workflow YAML.
CONCURRENCY_GROUPS: Mapping[str, str] = {
    "frontend-ci": "frontend-ci-${{ github.ref }}",
    "backend-ci": "backend-ci-${{ github.ref }}",
    "langgraph-ci": "langgraph-ci-${{ github.ref }}",
    "e2e-live": "e2e-live",
    "docker-build-publish": "docker-build-publish-${{ github.ref }}",
    "release": "release-${{ github.ref }}",
    "staging-deploy": "staging-deploy",
    "production-deploy": "production-deploy",
}


# Defensive consistency checks evaluated at import time so that any future
# divergence between WORKFLOWS and CONCURRENCY_GROUPS (e.g. someone adds a
# workflow to one but not the other) surfaces immediately when tests load
# the registry, rather than as a confusing KeyError deep in a test.
assert len(WORKFLOWS) == 8, "Design table C1 declares exactly eight workflows"
assert {wf.name for wf in WORKFLOWS} == set(CONCURRENCY_GROUPS), (
    "WORKFLOWS and CONCURRENCY_GROUPS must cover the same workflow names"
)
assert len(WORKFLOWS_BY_NAME) == len(WORKFLOWS), (
    "Workflow names in WORKFLOWS must be unique"
)
