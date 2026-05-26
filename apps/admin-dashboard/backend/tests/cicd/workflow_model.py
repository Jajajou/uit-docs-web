"""Pure model for GitHub Actions workflow trigger and path-filter semantics.

This module realises design data model D2 of the
``cicd-deploy-admin-dashboard`` spec. It exposes pure, side-effect-free
functions so the path-filter contract can be exercised with
property-based tests (correctness property CP-7) without standing up a
real GitHub Actions runtime.

The decisions encoded here mirror Requirement 1 of ``requirements.md``:

* A workflow is triggered iff (a) one of its declared triggers matches
  the inbound event, and (b) either it has no path filter or at least
  one changed file matches one of its glob patterns
  (Requirements 1.2 – 1.7).
* A workflow with an empty ``path_filter`` is always triggered when its
  trigger matches, regardless of the changed file set
  (Requirement 1.8).
* Glob matching uses :func:`fnmatch.fnmatchcase`, which treats ``*`` as
  "zero or more arbitrary characters" — including ``/`` — so patterns
  such as ``web/apps/admin-dashboard/frontend/**`` correctly match
  arbitrarily nested files under that directory.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Iterable, Literal


EventKind = Literal[
    "pull_request",
    "push",
    "tag_push",
    "schedule",
    "workflow_dispatch",
    "workflow_run",
]


@dataclass(frozen=True)
class Event:
    """A workflow-triggering event.

    Attributes:
        kind: The category of event observed in GitHub Actions.
        ref: The git ref associated with the event. For ``push`` events
            this is typically ``refs/heads/<branch>``; for ``tag_push``
            events it is ``refs/tags/<tag>``; for non-filesystem events
            (``schedule``, ``workflow_dispatch``, ``workflow_run``) the
            ref may be empty.
        changed_files: The set of repository-relative paths touched by
            the event. Empty for non-filesystem events.
    """

    kind: EventKind
    ref: str
    changed_files: frozenset[str]


@dataclass(frozen=True)
class Workflow:
    """A declarative GitHub Actions workflow definition.

    Attributes:
        name: The workflow's logical name — by convention the basename
            of the YAML file without the ``.yml`` extension.
        file_path: The repository-relative path of the workflow YAML
            (e.g. ``.github/workflows/frontend-ci.yml``).
        triggers: The encoded trigger set. Each entry is either a bare
            event kind (``"pull_request"``, ``"workflow_dispatch"``,
            ``"schedule"``, ``"workflow_run"``) or a kind plus
            qualifier separated by ``:``. Recognised qualified forms:

            * ``"push:<branch>"`` — push to a specific branch.
            * ``"push:tags <glob>"`` — tag push whose tag name matches
              ``<glob>`` via :func:`fnmatch.fnmatchcase`.
            * ``"schedule:<cron>"`` — schedule trigger (the cron
              expression is preserved for documentation but does not
              constrain matching here).
            * ``"workflow_run:<spec>"`` — workflow-run trigger
              (the ``<spec>`` portion is preserved for documentation).
        path_filter: Glob patterns evaluated against
            ``Event.changed_files`` using :func:`fnmatch.fnmatchcase`.
            An empty tuple means the workflow has no path filter and
            therefore matches whenever its trigger matches
            (Requirement 1.8).
    """

    name: str
    file_path: str
    triggers: frozenset[str]
    path_filter: tuple[str, ...]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ref_branch(ref: str) -> str:
    """Return the branch portion of ``refs/heads/<branch>``.

    Falls back to the raw ref when the prefix is absent so that callers
    can still pass bare branch names in tests.
    """
    prefix = "refs/heads/"
    return ref[len(prefix):] if ref.startswith(prefix) else ref


def _ref_tag(ref: str) -> str:
    """Return the tag portion of ``refs/tags/<tag>``.

    Falls back to the raw ref when the prefix is absent.
    """
    prefix = "refs/tags/"
    return ref[len(prefix):] if ref.startswith(prefix) else ref


def _single_trigger_matches(trigger: str, event: Event) -> bool:
    """Return True iff ``trigger`` matches ``event``.

    See :class:`Workflow` for the full trigger grammar.
    """
    kind, sep, qualifier = trigger.partition(":")
    kind = kind.strip()
    qualifier = qualifier.strip()

    if kind == "pull_request":
        return event.kind == "pull_request"

    if kind == "push":
        # ``push`` triggers cover both branch pushes and tag pushes,
        # depending on the qualifier.
        if event.kind == "push":
            if not qualifier:
                return True
            return _ref_branch(event.ref) == qualifier
        if event.kind == "tag_push" and qualifier.startswith("tags"):
            # Accept both ``tags`` (no glob) and ``tags <glob>``.
            tail = qualifier[len("tags"):].strip()
            tag = _ref_tag(event.ref)
            if not tail:
                return True
            return fnmatch.fnmatchcase(tag, tail)
        return False

    if kind == "schedule":
        return event.kind == "schedule"

    if kind == "workflow_dispatch":
        return event.kind == "workflow_dispatch"

    if kind == "workflow_run":
        return event.kind == "workflow_run"

    return False


def _trigger_matches(workflow: Workflow, event: Event) -> bool:
    """Return True iff any of ``workflow.triggers`` matches ``event``."""
    return any(_single_trigger_matches(t, event) for t in workflow.triggers)


def _path_filter_matches(
    patterns: tuple[str, ...], changed_files: Iterable[str]
) -> bool:
    """Return True iff some changed file matches some pattern.

    Uses :func:`fnmatch.fnmatchcase` so that ``*`` matches any
    character (including ``/``), which makes ``a/b/**`` match
    arbitrarily nested files under ``a/b/`` as required by
    Requirements 1.2 – 1.4.
    """
    files = tuple(changed_files)
    if not files or not patterns:
        return False
    return any(
        fnmatch.fnmatchcase(f, p) for f in files for p in patterns
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def matches(workflow: Workflow, event: Event) -> bool:
    """Return True iff ``event`` triggers ``workflow``.

    Mirrors the pseudocode in design D2:

    1. The workflow's trigger set must contain at least one entry that
       matches the event (kind plus optional qualifier).
    2. If the workflow has no path filter, the match succeeds
       (Requirement 1.8).
    3. Otherwise, at least one changed file must match at least one
       path-filter pattern under :func:`fnmatch.fnmatchcase`
       (Requirements 1.2 – 1.7).
    """
    if not _trigger_matches(workflow, event):
        return False
    if not workflow.path_filter:
        return True
    return _path_filter_matches(workflow.path_filter, event.changed_files)


def triggered_workflows(
    event: Event, workflows: Iterable[Workflow]
) -> set[str]:
    """Return the names of workflows triggered by ``event``.

    The returned set contains exactly the names of those workflows in
    ``workflows`` for which :func:`matches` is True.
    """
    return {w.name for w in workflows if matches(w, event)}


__all__ = [
    "Event",
    "EventKind",
    "Workflow",
    "matches",
    "triggered_workflows",
]
