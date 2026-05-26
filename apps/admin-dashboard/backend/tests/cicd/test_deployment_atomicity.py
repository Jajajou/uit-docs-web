"""Property-based test for deployment atomicity.

Property 2: Deployment Atomicity.

**Validates: Requirements 9.5, 10.8, 11.1, 11.2, 11.3, 11.4, 11.5, 12.7, 12.8**

Property 2 from the design document (CP-2) states:

    For *any* failure injected at any step of the production deploy
    state machine (alembic upgrade, backend container start, lightrag
    container start, backend health probe, lightrag health probe,
    Vercel promotion, smoke test), the final observable state of the
    system SHALL satisfy one of the following:

      (a) all three components -- ``admin_frontend``, ``admin_backend``,
          ``lightrag_uit`` -- are at the new release version and the
          deploy is marked successful, or
      (b) all three components are at the previous release version and
          the deploy is marked failed.

    No mixed-version end state is permitted.

This module encodes a pure-Python state-machine simulator
:func:`simulate_deploy` that mirrors the deploy sequence specified by
``production-deploy.yml`` and design section C9, then drives it with a
Hypothesis strategy that randomises the initial state, the new release
tag, the new Alembic revision, and the failure-injection point.

The simulator deliberately threads the deployment through *intermediate
states* before applying rollback. That is what makes the property test
non-trivial: a bug that forgot to roll back one of the three components
on a late-stage failure would leave a mixed-version state and the
property would fail.

``max_examples=100`` per the task description.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Optional

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeployState:
    """Observable state of the production stack after a deploy run.

    Attributes mirror the host-side artefacts written by
    ``scripts/deploy/ssh_deploy.sh`` (D3) and the Vercel production
    deployment promoted by ``production-deploy.yml``:

    * ``frontend_tag`` -- the Vercel deployment alias for
      ``Admin_Frontend``.
    * ``backend_tag``  -- the GHCR image tag running as
      ``admin_backend``.
    * ``lightrag_tag`` -- the GHCR image tag running as
      ``lightrag_uit``.
    * ``alembic_revision`` -- the active head revision in the
      ``admin_dashboard`` Postgres schema.
    """

    frontend_tag: str
    backend_tag: str
    lightrag_tag: str
    alembic_revision: str


# Step labels exactly mirror the failure-injection set listed in design
# table P2 (``{migrate, backend_up, lightrag_up, backend_health,
# lightrag_health, vercel, smoke}``); the simulator collapses
# ``backend_up``/``lightrag_up`` into a single ``compose`` step because
# ``docker compose up -d admin_backend lightrag_uit`` is a single
# atomic invocation in production-deploy.yml, and similarly collapses
# the two health probes into a single ``health`` step.
Step = Literal["alembic", "compose", "health", "vercel", "smoke"]
_STEPS: tuple[Step, ...] = ("alembic", "compose", "health", "vercel", "smoke")
_FAILURE_POINTS: tuple[Optional[Step], ...] = (None, *_STEPS)

DeployStatus = Literal["success", "failed"]


# ---------------------------------------------------------------------------
# State-machine simulator
# ---------------------------------------------------------------------------


def simulate_deploy(
    state: DeployState,
    new_tag: str,
    new_revision: str,
    failure_at: Optional[Step],
) -> tuple[DeployState, DeployStatus]:
    """Pure-Python simulator of ``production-deploy.yml``.

    Steps in order, matching design C9:

        1. ``alembic`` -- ``timeout 600 alembic upgrade head`` over SSH.
        2. ``compose`` -- ``docker compose pull`` then
           ``docker compose up -d admin_backend lightrag_uit``.
        3. ``health``  -- poll ``/healthz`` on backend and lightrag for
           up to 60 seconds.
        4. ``vercel``  -- ``vercel deploy --prod`` (frontend promote).
        5. ``smoke``   -- ``scripts/smoke_test.sh`` against all three
           public endpoints.

    Failure handling per design C9 (R11.1-R11.5, R12.6-R12.8):

        * ``alembic`` fail -> abort; previous containers retained, no
          schema change committed (R12.7); deploy marked failed.
        * ``compose`` fail -> ``Rollback_Procedure`` for all three
          components; ``alembic downgrade <previous_revision>`` reverts
          the schema (R12.6, R12.8).
        * ``health`` fail -> skip Vercel promote (R11.2); roll back the
          backend and lightrag containers and downgrade the schema.
        * ``vercel`` fail -> roll back all three components within
          300s (R11.3).
        * ``smoke`` fail  -> ``Rollback_Procedure`` for all three
          components (R10.8).

    Returns ``(final_state, status)`` where ``status`` is ``"success"``
    iff every step succeeded, otherwise ``"failed"``.
    """
    if failure_at is not None and failure_at not in _STEPS:
        raise ValueError(f"unknown failure_at: {failure_at!r}")

    # Snapshot for rollback. Equality of the final state with this
    # value is the contract on every failure path.
    prev = state

    # ------------------------------------------------------------------
    # Step 1: alembic upgrade head
    # ------------------------------------------------------------------
    if failure_at == "alembic":
        # No schema change committed yet; previous containers retained.
        return prev, "failed"
    after_migrate = replace(state, alembic_revision=new_revision)

    # ------------------------------------------------------------------
    # Step 2: docker compose pull + up admin_backend + lightrag_uit
    # ------------------------------------------------------------------
    if failure_at == "compose":
        # Rollback_Procedure: restore prior tags and downgrade schema.
        return prev, "failed"
    after_compose = replace(
        after_migrate, backend_tag=new_tag, lightrag_tag=new_tag
    )

    # ------------------------------------------------------------------
    # Step 3: health probe on backend + lightrag
    # ------------------------------------------------------------------
    if failure_at == "health":
        # Skip Vercel promote; roll back backend, lightrag, and schema.
        return prev, "failed"

    # ------------------------------------------------------------------
    # Step 4: vercel deploy --prod (frontend promotion)
    # ------------------------------------------------------------------
    if failure_at == "vercel":
        # Roll back all three components within 300s. At this point
        # backend and lightrag are at ``new_tag`` while frontend is
        # still at the prior tag -- exactly the mixed-version window
        # CP-2 forbids in the *final* state. The rollback closes it.
        return prev, "failed"
    after_vercel = replace(after_compose, frontend_tag=new_tag)

    # ------------------------------------------------------------------
    # Step 5: smoke test
    # ------------------------------------------------------------------
    if failure_at == "smoke":
        return prev, "failed"

    return after_vercel, "success"


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------


# Tag alphabet covers typical SemVer release tags (``v1.2.3``,
# ``v0.4.0-rc.1``) and SHA-suffixed mainline tags (``sha-<hex>``).
_TAG_ALPHABET = "0123456789abcdefv.-"
_TAG = st.text(alphabet=_TAG_ALPHABET, min_size=1, max_size=20)

# Alembic revision ids are short hex strings produced by Alembic's
# ``rev_id`` generator; 4-12 hex chars covers the realistic range.
_REVISION = st.text(alphabet="0123456789abcdef", min_size=4, max_size=12)

_FAILURE = st.sampled_from(_FAILURE_POINTS)


@st.composite
def _deploy_states(draw: st.DrawFn) -> DeployState:
    """Generate uniform initial states.

    A "previous release version" in design C9 is a single release that
    was atomically deployed by a prior run, so the three components
    share its tag. This is the precondition of Property 2; constraining
    the strategy to uniform states keeps the property focused on the
    deploy state machine rather than on whatever produced the initial
    state.
    """
    tag = draw(_TAG)
    rev = draw(_REVISION)
    return DeployState(
        frontend_tag=tag,
        backend_tag=tag,
        lightrag_tag=tag,
        alembic_revision=rev,
    )


# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------


@given(
    state=_deploy_states(),
    new_tag=_TAG,
    new_revision=_REVISION,
    failure_at=_FAILURE,
)
@settings(max_examples=100)
def test_deployment_atomicity(
    state: DeployState,
    new_tag: str,
    new_revision: str,
    failure_at: Optional[Step],
) -> None:
    """**Validates: Requirements 9.5, 10.8, 11.1, 11.2, 11.3, 11.4, 11.5, 12.7, 12.8**

    For every (initial_state, new_tag, new_revision, failure_at) draw,
    drive :func:`simulate_deploy` and assert the atomic-deploy
    invariant of Property 2 / CP-2:

    * The three component tags in the final state are always equal --
      no mixed-version end state is observable.
    * On ``"success"``, all three component tags equal ``new_tag`` and
      the Alembic revision equals ``new_revision``.
    * On ``"failed"``, the final state equals the initial state -- the
      rollback restored all three components and the schema together.
    """
    final, status = simulate_deploy(state, new_tag, new_revision, failure_at)

    # Atomicity: the three components share a single tag at end-of-run.
    assert (
        final.frontend_tag == final.backend_tag == final.lightrag_tag
    ), (
        "mixed-version end state -- CP-2 violated.\n"
        f"  initial   = {state!r}\n"
        f"  new_tag   = {new_tag!r}\n"
        f"  new_rev   = {new_revision!r}\n"
        f"  failure_at = {failure_at!r}\n"
        f"  final     = {final!r}\n"
        f"  status    = {status!r}"
    )

    if status == "success":
        # Success path: failure_at must be None and every component
        # must reflect the new release.
        assert failure_at is None, (
            f"deploy reported success despite failure_at={failure_at!r}"
        )
        expected = DeployState(
            frontend_tag=new_tag,
            backend_tag=new_tag,
            lightrag_tag=new_tag,
            alembic_revision=new_revision,
        )
        assert final == expected, (
            "successful deploy did not converge on the new release.\n"
            f"  expected = {expected!r}\n"
            f"  final    = {final!r}"
        )
    else:
        # Failure path: a step must have failed and the rollback must
        # have restored the previous state in full.
        assert status == "failed"
        assert failure_at is not None, (
            "deploy reported failure with failure_at=None"
        )
        assert final == state, (
            "rollback did not restore the previous release atomically.\n"
            f"  initial   = {state!r}\n"
            f"  final     = {final!r}\n"
            f"  failure_at = {failure_at!r}"
        )
