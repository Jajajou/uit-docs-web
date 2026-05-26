"""Property-based test for path-filter correctness.

Property 1: Path-Filter Correctness.

**Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**

For every (event, changed_files) pair, the set returned by
:func:`tests.cicd.workflow_model.triggered_workflows` must equal::

    { w in WORKFLOWS : trigger_matches(w, event)
                       and (w.path_filter is empty
                            or any file in event.changed_files matches
                               any pattern in w.path_filter) }

The expected set is computed here from a small, deliberately *independent*
reference implementation -- it does not call any private helper of
``workflow_model``. That keeps the property test from collapsing into
``f(x) == f(x)`` while still being a faithful encoding of the contract
documented on :class:`tests.cicd.workflow_model.Workflow`.

Strategy:

* ``repo_files()`` returns a fixed list of repository-relative paths that
  collectively touch every workflow's path filter (plus a few paths that
  intentionally match no filter, so we exercise the "no overlap" branch).
* Hypothesis draws a *subset* of those files via
  ``sets(sampled_from(repo_files()))``.
* Hypothesis also draws an event "kind label" via ``sampled_from`` covering
  ``pull_request``, ``push:main``, ``push:<feature-branch>``,
  ``tag_push v*``, ``schedule``, ``workflow_dispatch``, and
  ``workflow_run`` -- the seven event shapes that any of the eight
  workflows declared in design table C1 can react to.
* ``max_examples=100`` per task 2.2.
"""

from __future__ import annotations

import fnmatch
from typing import Iterable

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.cicd.workflow_model import Event, Workflow, triggered_workflows
from tests.cicd.workflow_registry import WORKFLOWS


# ---------------------------------------------------------------------------
# Fixed repo_files() corpus
# ---------------------------------------------------------------------------


def repo_files() -> tuple[str, ...]:
    """Return a fixed list of repo-relative paths for the property test.

    The list is constructed so that each of the eight workflows' path
    filters has at least one matching file *and* at least one path is
    included that matches no filter at all. Hypothesis then samples
    arbitrary subsets of this list.
    """
    return (
        # ----- frontend-ci path filter -------------------------------------
        "web/apps/admin-dashboard/frontend/src/App.tsx",
        "web/apps/admin-dashboard/frontend/package.json",
        ".github/workflows/frontend-ci.yml",
        # ----- backend-ci path filter --------------------------------------
        "web/apps/admin-dashboard/backend/app/main.py",
        "web/apps/admin-dashboard/backend/requirements.txt",
        ".github/workflows/backend-ci.yml",
        # ----- langgraph-ci path filter ------------------------------------
        "LangGraph/agent.py",
        "LangGraph/tests/test_agent.py",
        ".github/workflows/langgraph-ci.yml",
        # ----- other workflow YAMLs (always-on workflows have no filter,
        # so these are present mainly to vary the changed-file mix) --------
        ".github/workflows/e2e-live.yml",
        ".github/workflows/docker-build-publish.yml",
        ".github/workflows/release.yml",
        ".github/workflows/staging-deploy.yml",
        ".github/workflows/production-deploy.yml",
        # ----- paths intentionally outside every path filter ---------------
        "docs/runbooks/admin-dashboard.md",
        "unrelated/file.txt",
        "README.md",
    )


_REPO_FILES: tuple[str, ...] = repo_files()


# ---------------------------------------------------------------------------
# Independent reference implementation of the matching contract
# ---------------------------------------------------------------------------


def _ref_branch(ref: str) -> str:
    prefix = "refs/heads/"
    return ref[len(prefix):] if ref.startswith(prefix) else ref


def _ref_tag(ref: str) -> str:
    prefix = "refs/tags/"
    return ref[len(prefix):] if ref.startswith(prefix) else ref


def _trigger_matches_event(trigger: str, event: Event) -> bool:
    """Independent reference impl of the trigger contract documented on
    :class:`tests.cicd.workflow_model.Workflow`.

    Recognised forms:
        * ``pull_request``
        * ``push`` / ``push:<branch>`` -- branch push
        * ``push:tags`` / ``push:tags <glob>`` -- tag push
        * ``schedule`` / ``schedule:<cron>``
        * ``workflow_dispatch``
        * ``workflow_run`` / ``workflow_run:<spec>``

    Any other shape fails closed (returns ``False``); this mirrors the
    fall-through behaviour documented in the model and ensures the test
    detects regressions where a new trigger keyword is silently accepted.
    """
    kind, _, qualifier = trigger.partition(":")
    kind = kind.strip()
    qualifier = qualifier.strip()

    if kind == "pull_request":
        return event.kind == "pull_request"
    if kind == "push":
        if event.kind == "push":
            return not qualifier or _ref_branch(event.ref) == qualifier
        if event.kind == "tag_push" and qualifier.startswith("tags"):
            tail = qualifier[len("tags"):].strip()
            tag = _ref_tag(event.ref)
            return not tail or fnmatch.fnmatchcase(tag, tail)
        return False
    if kind == "schedule":
        return event.kind == "schedule"
    if kind == "workflow_dispatch":
        return event.kind == "workflow_dispatch"
    if kind == "workflow_run":
        return event.kind == "workflow_run"
    return False


def _path_filter_overlaps(
    patterns: tuple[str, ...], changed_files: Iterable[str]
) -> bool:
    """Return True iff at least one ``f`` matches at least one ``p``.

    Uses :func:`fnmatch.fnmatchcase` so ``*`` matches arbitrary characters
    including ``/``, mirroring the GitHub ``paths:`` glob semantics.
    """
    files = tuple(changed_files)
    if not files or not patterns:
        return False
    return any(
        fnmatch.fnmatchcase(f, p) for f in files for p in patterns
    )


def _expected_triggered(
    event: Event, workflows: Iterable[Workflow]
) -> set[str]:
    """Independent reference computation of Property 1.

    Includes ``w.name`` iff:
        (a) at least one of ``w.triggers`` matches the event, and
        (b) ``w.path_filter`` is empty, or some changed file matches some
            pattern in ``w.path_filter``.
    """
    out: set[str] = set()
    for wf in workflows:
        if not any(_trigger_matches_event(t, event) for t in wf.triggers):
            continue
        if not wf.path_filter:
            out.add(wf.name)
            continue
        if _path_filter_overlaps(wf.path_filter, event.changed_files):
            out.add(wf.name)
    return out


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------


_FILES_STRATEGY = st.sets(st.sampled_from(_REPO_FILES))

# Each label encodes the *shape* of a synthetic event and what additional
# data must be drawn to materialise it. Doing this via ``sampled_from``
# (rather than ``one_of``) gives Hypothesis a uniform shrink target and
# keeps the strategy easy to read.
_EVENT_LABELS: tuple[str, ...] = (
    "pull_request",
    "push:main",
    "push:feature",
    "tag_push:v*",
    "tag_push:other",
    "schedule",
    "workflow_dispatch",
    "workflow_run",
)


@st.composite
def _events(draw: st.DrawFn) -> Event:
    files = frozenset(draw(_FILES_STRATEGY))
    label = draw(st.sampled_from(_EVENT_LABELS))

    if label == "pull_request":
        return Event(
            kind="pull_request",
            ref="refs/heads/feature/x",
            changed_files=files,
        )
    if label == "push:main":
        return Event(
            kind="push", ref="refs/heads/main", changed_files=files
        )
    if label == "push:feature":
        return Event(
            kind="push",
            ref="refs/heads/feature/x",
            changed_files=files,
        )
    if label == "tag_push:v*":
        tag = draw(st.sampled_from(["v1.0.0", "v2.3.4", "v0.1.0-rc.1"]))
        return Event(
            kind="tag_push",
            ref=f"refs/tags/{tag}",
            changed_files=files,
        )
    if label == "tag_push:other":
        tag = draw(st.sampled_from(["release-1", "internal-build", "x"]))
        return Event(
            kind="tag_push",
            ref=f"refs/tags/{tag}",
            changed_files=files,
        )
    if label == "schedule":
        # ``schedule`` events have no ref or files in GitHub Actions, but
        # we keep the sampled file set on the event to exercise the rule
        # that path filters never apply when triggers don't match.
        return Event(kind="schedule", ref="", changed_files=files)
    if label == "workflow_dispatch":
        return Event(
            kind="workflow_dispatch", ref="", changed_files=files
        )
    # workflow_run
    return Event(kind="workflow_run", ref="", changed_files=files)


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


@given(event=_events())
@settings(max_examples=100)
def test_path_filter_correctness(event: Event) -> None:
    """**Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**

    For every event/changed-files combination, the set of triggered
    workflows returned by :func:`triggered_workflows` equals the set
    produced by the independent reference computation in
    :func:`_expected_triggered`. This is Property 1 from the design
    document.
    """
    actual = triggered_workflows(event, WORKFLOWS)
    expected = _expected_triggered(event, WORKFLOWS)

    assert actual == expected, (
        "triggered_workflows disagrees with the path-filter contract.\n"
        f"  event = {event!r}\n"
        f"  actual = {sorted(actual)!r}\n"
        f"  expected = {sorted(expected)!r}\n"
        f"  symmetric_difference = {sorted(actual ^ expected)!r}"
    )
