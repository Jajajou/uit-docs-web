"""Property-based test for PR status comment idempotency.

Property 17: PR Status Comment Idempotency.

**Validates: Requirements 21.2, 21.3, 21.4**

For any finite sequence of workflow-run completions associated with a
single PR, after the last completion has been processed by the PR-status
reusable workflow, exactly one summary comment authored by
``github-actions[bot]`` and bearing the marker
``<!-- pr-status-summary:v1 -->`` SHALL exist on that PR, and its body
SHALL reflect the most recent run's results. No other comments authored
by ``github-actions[bot]`` on that PR SHALL be modified.

The mocked :class:`IssuesAPI` and the :func:`apply_workflow_run` driver
below are a faithful Python port of the github-script step in
``.github/workflows/pr-status-summary.yml`` (design C16): list comments,
filter to the one whose body starts with the marker and is authored by
``github-actions[bot]``, edit it in place if found, otherwise create
exactly one. The marker comment is the idempotency token.

Strategy:

* ``WORKFLOW_NAMES`` covers the eight workflows from Requirement 1.1.
* ``CONCLUSIONS`` covers every workflow-run conclusion the YAML maps onto
  the GitHub commit-status state domain (``success``, ``failure``,
  ``cancelled``, ``timed_out``, ``skipped``).
* For each example we pre-seed the API with 1-2 ``github-actions[bot]``
  comments whose bodies do **not** start with the marker (chosen from a
  restricted alphabet so accidental collision is impossible) and 1
  comment from a non-bot user, so that the "never modify any other
  comment" clause (R21.4) is exercised.
* Hypothesis draws a list of 1-20 ``(workflow_name, conclusion)`` tuples
  and applies them in order via :func:`apply_workflow_run`.
* ``max_examples=100`` per the task spec.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Mocks of the GitHub Issues API surface used by the github-script step
# ---------------------------------------------------------------------------


MARKER = "<!-- pr-status-summary:v1 -->"
BOT_LOGIN = "github-actions[bot]"


@dataclass
class Comment:
    """Minimal mirror of the GitHub Issues comment object.

    Only the three fields the github-script step reads are modelled:
    ``id`` (used as the update target), ``user.login`` (used to filter
    to bot comments), and ``body`` (used to detect the marker prefix and
    to write the new summary).
    """

    id: int
    user_login: str
    body: str


class IssuesAPI:
    """In-memory mock of the GitHub Issues comments API.

    Mirrors the three operations the github-script step invokes:
    :meth:`list_comments`, :meth:`create_comment`, and
    :meth:`update_comment`. Returned :class:`Comment` instances are
    copies so callers cannot mutate stored state via aliasing -- this
    matches the wire-level GitHub API where each call returns a fresh
    JSON payload.
    """

    def __init__(self, comments: Optional[list[Comment]] = None) -> None:
        self._comments: list[Comment] = [replace(c) for c in (comments or [])]
        self._next_id: int = 1 + max((c.id for c in self._comments), default=0)

    def list_comments(self) -> list[Comment]:
        return [replace(c) for c in self._comments]

    def create_comment(self, body: str, user_login: str = BOT_LOGIN) -> Comment:
        new = Comment(id=self._next_id, user_login=user_login, body=body)
        self._next_id += 1
        self._comments.append(new)
        return replace(new)

    def update_comment(self, comment_id: int, body: str) -> None:
        for idx, current in enumerate(self._comments):
            if current.id == comment_id:
                self._comments[idx] = Comment(
                    id=current.id, user_login=current.user_login, body=body
                )
                return
        raise KeyError(f"comment id {comment_id} not found")


# ---------------------------------------------------------------------------
# Python port of the github-script step
# ---------------------------------------------------------------------------


def _icon_for(conclusion: str) -> str:
    """Mirror the ``iconFor`` switch in pr-status-summary.yml."""
    return {
        "success": ":white_check_mark:",
        "failure": ":x:",
        "cancelled": ":no_entry_sign:",
        "skipped": ":fast_forward:",
        "timed_out": ":alarm_clock:",
    }.get(conclusion, ":grey_question:")


def build_summary_body(
    head_sha: str, workflow_name: str, conclusion: str, updated_at: str
) -> str:
    """Build the marker-prefixed summary body posted by the workflow.

    Identical in structure to the body assembled inside
    ``pr-status-summary.yml``. ``updated_at`` is plumbed through as a
    parameter so each call to :func:`apply_workflow_run` produces a
    deterministically-distinct body, which makes the "body reflects the
    latest run" assertion strict (the latest call's body cannot
    accidentally collide with any earlier call's body).
    """
    short_sha = head_sha[:7]
    return "\n".join(
        [
            MARKER,
            "",
            "## CI/CD Workflow Summary",
            "",
            f"Commit: `{short_sha}`",
            "",
            "| Workflow | Status | Result |",
            "| --- | --- | --- |",
            f"| {workflow_name} | {_icon_for(conclusion)} | {conclusion} |",
            "",
            f"_Last updated by {workflow_name} at {updated_at}._",
        ]
    )


def apply_workflow_run(
    api: IssuesAPI,
    head_sha: str,
    workflow_name: str,
    conclusion: str,
    updated_at: str,
) -> None:
    """Mirror the github-script comment-update logic.

    1. List all comments on the issue.
    2. Filter to comments authored by ``github-actions[bot]`` whose body
       starts with the marker.
    3. If none, create exactly one new comment with the new body
       (R21.3).
    4. Otherwise, edit the oldest marker comment in place (R21.2). Any
       other comment -- including duplicate marker comments, non-marker
       bot comments, and user comments -- is left untouched (R21.4).
    """
    body = build_summary_body(head_sha, workflow_name, conclusion, updated_at)
    comments = api.list_comments()
    marker_comments = [
        c
        for c in comments
        if c.user_login == BOT_LOGIN and c.body.startswith(MARKER)
    ]
    if not marker_comments:
        api.create_comment(body=body, user_login=BOT_LOGIN)
        return
    target = min(marker_comments, key=lambda c: c.id)
    api.update_comment(comment_id=target.id, body=body)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------


# The eight workflows listed in Requirement 1.1 / design table C1.
WORKFLOW_NAMES: tuple[str, ...] = (
    "frontend-ci",
    "backend-ci",
    "langgraph-ci",
    "e2e-live",
    "docker-build-publish",
    "release",
    "staging-deploy",
    "production-deploy",
)

# Every workflow_run.conclusion the YAML maps onto a status state.
CONCLUSIONS: tuple[str, ...] = (
    "success",
    "failure",
    "cancelled",
    "timed_out",
    "skipped",
)

# Restricted alphabet for seed comment bodies. The marker
# ``<!-- pr-status-summary:v1 -->`` requires ``<``, ``!``, and ``:`` --
# none of which are in this alphabet -- so seed bodies cannot
# accidentally trigger the marker filter.
_SEED_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789 .-_"

_run_strategy = st.tuples(
    st.sampled_from(WORKFLOW_NAMES),
    st.sampled_from(CONCLUSIONS),
)


@st.composite
def _scenarios(draw: st.DrawFn) -> tuple:
    """Draw a full property-test scenario.

    Returned tuple:
        (head_sha, runs, bot_seed_bodies, user_seed_body, user_login)

    where ``runs`` is a non-empty list of ``(workflow_name, conclusion)``
    tuples to be applied in order, ``bot_seed_bodies`` is a 1-2 element
    tuple of pre-seeded ``github-actions[bot]`` comment bodies that do
    not start with the marker, and ``user_seed_body``/``user_login``
    describe a single non-bot comment.
    """
    head_sha = draw(
        st.text(alphabet="0123456789abcdef", min_size=40, max_size=40)
    )
    runs = draw(st.lists(_run_strategy, min_size=1, max_size=20))
    n_bot_seed = draw(st.integers(min_value=1, max_value=2))
    bot_seed_bodies = tuple(
        draw(st.text(alphabet=_SEED_ALPHABET, min_size=1, max_size=40))
        for _ in range(n_bot_seed)
    )
    user_seed_body = draw(
        st.text(alphabet=_SEED_ALPHABET, min_size=1, max_size=40)
    )
    user_login = draw(st.sampled_from(["alice", "bob", "carol"]))
    return head_sha, runs, bot_seed_bodies, user_seed_body, user_login


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


@given(_scenarios())
@settings(max_examples=100)
def test_pr_status_comment_idempotency(scenario: tuple) -> None:
    """**Validates: Requirements 21.2, 21.3, 21.4**

    Property 17. After applying any non-empty sequence of workflow-run
    completions, the PR comment state SHALL satisfy:

    * Exactly one comment authored by ``github-actions[bot]`` whose
      body starts with ``<!-- pr-status-summary:v1 -->`` exists
      (R21.2 + R21.3 -- the workflow neither duplicates nor drops the
      marker comment).
    * That marker comment's body equals the body that the latest run
      would produce.
    * Every pre-seeded comment (other bot comments and user comments)
      retains its original ``user_login`` and ``body`` (R21.4).
    * No new comments are created beyond the single marker comment;
      the total comment count is exactly ``len(seed) + 1``.
    """
    head_sha, runs, bot_seed_bodies, user_seed_body, user_login = scenario

    # Build the seed corpus: 1-2 non-marker bot comments plus 1 user
    # comment. Ids start at 1 and increment so we know which ids
    # belonged to the seed (everything else is created by the workflow).
    seed_comments: list[Comment] = []
    next_id = 1
    for body in bot_seed_bodies:
        seed_comments.append(
            Comment(id=next_id, user_login=BOT_LOGIN, body=body)
        )
        next_id += 1
    seed_comments.append(
        Comment(id=next_id, user_login=user_login, body=user_seed_body)
    )

    api = IssuesAPI(comments=seed_comments)
    seed_snapshot = {c.id: replace(c) for c in seed_comments}

    # Drive the simulated workflow_run completions in order. The
    # ``updated_at`` token is keyed by sequence index so the body of
    # each call is distinct from every prior call's body.
    for i, (workflow_name, conclusion) in enumerate(runs):
        apply_workflow_run(
            api,
            head_sha=head_sha,
            workflow_name=workflow_name,
            conclusion=conclusion,
            updated_at=f"step-{i}",
        )

    final = api.list_comments()

    # 1. Exactly one marker comment from the bot.
    marker_comments = [
        c
        for c in final
        if c.user_login == BOT_LOGIN and c.body.startswith(MARKER)
    ]
    assert len(marker_comments) == 1, (
        "expected exactly one marker comment after sequence; "
        f"got {len(marker_comments)} (final={final!r})"
    )

    # 2. Body reflects the latest run.
    last_workflow, last_conclusion = runs[-1]
    expected_body = build_summary_body(
        head_sha,
        last_workflow,
        last_conclusion,
        f"step-{len(runs) - 1}",
    )
    assert marker_comments[0].body == expected_body, (
        "marker comment body does not reflect the latest run.\n"
        f"  last run = ({last_workflow!r}, {last_conclusion!r})\n"
        f"  expected = {expected_body!r}\n"
        f"  actual   = {marker_comments[0].body!r}"
    )

    # 3. Every pre-seeded comment is unchanged.
    for c in final:
        if c.id in seed_snapshot:
            original = seed_snapshot[c.id]
            assert c.user_login == original.user_login, (
                f"seed comment id={c.id} user_login changed: "
                f"{original.user_login!r} -> {c.user_login!r}"
            )
            assert c.body == original.body, (
                f"seed comment id={c.id} (user={original.user_login!r}) "
                f"body was modified: {original.body!r} -> {c.body!r}"
            )

    # 4. The workflow created at most one new comment, regardless of
    #    how many times it was invoked.
    new_ids = {c.id for c in final} - set(seed_snapshot)
    assert len(new_ids) == 1, (
        f"expected exactly one new comment id beyond the seed corpus, "
        f"got {sorted(new_ids)!r}"
    )
    assert marker_comments[0].id in new_ids, (
        "the marker comment must be the newly-created comment, not a "
        "modified seed comment"
    )


# ---------------------------------------------------------------------------
# Example-based tests anchoring the three concrete branches of Property 17
# ---------------------------------------------------------------------------


def test_first_run_creates_marker_comment_when_none_exists() -> None:
    """**Validates: Requirements 21.3**

    With only non-marker comments in place, the first workflow_run
    completion creates exactly one marker comment from the bot.
    """
    seed = [
        Comment(id=1, user_login=BOT_LOGIN, body="dependabot rebase"),
        Comment(id=2, user_login="alice", body="LGTM"),
    ]
    api = IssuesAPI(comments=seed)

    apply_workflow_run(
        api,
        head_sha="abc1234def5678",
        workflow_name="backend-ci",
        conclusion="success",
        updated_at="step-0",
    )

    final = api.list_comments()
    marker = [
        c for c in final if c.user_login == BOT_LOGIN and c.body.startswith(MARKER)
    ]
    assert len(marker) == 1
    assert marker[0].id == 3
    # Seed unchanged.
    assert final[0].body == "dependabot rebase"
    assert final[1].body == "LGTM"


def test_subsequent_runs_edit_marker_in_place() -> None:
    """**Validates: Requirements 21.2, 21.4**

    A second workflow_run completion edits the existing marker comment
    in place rather than creating a duplicate, and leaves every other
    comment untouched.
    """
    seed = [
        Comment(id=1, user_login=BOT_LOGIN, body="codecov report"),
        Comment(id=2, user_login="alice", body="please rebase"),
    ]
    api = IssuesAPI(comments=seed)

    apply_workflow_run(
        api,
        head_sha="abc1234def5678",
        workflow_name="frontend-ci",
        conclusion="failure",
        updated_at="step-0",
    )
    apply_workflow_run(
        api,
        head_sha="abc1234def5678",
        workflow_name="backend-ci",
        conclusion="success",
        updated_at="step-1",
    )

    final = api.list_comments()
    marker = [
        c for c in final if c.user_login == BOT_LOGIN and c.body.startswith(MARKER)
    ]
    assert len(marker) == 1
    expected = build_summary_body(
        "abc1234def5678", "backend-ci", "success", "step-1"
    )
    assert marker[0].body == expected
    # Seed unchanged.
    assert final[0].body == "codecov report"
    assert final[1].body == "please rebase"
    # Total = 2 seeds + 1 created marker.
    assert len(final) == 3
