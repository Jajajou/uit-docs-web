"""Property-based test for the CI idempotency replay diff model.

Property 8: CI Idempotency.

**Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3**

For any commit SHA ``c`` and any workflow ``W ∈ {frontend-ci, backend-ci,
langgraph-ci}``, two runs of ``W`` against ``c`` on the same runner image
and same lockfiles SHALL produce the same workflow conclusion
(``success`` or ``failure``), the same set of test names, and the same
set of uploaded artifact filenames.

The script under test is ``scripts/ci/idempotency_diff.sh`` which compares
two replay summary directories (``conclusion.txt``, ``artifacts.txt``,
optional JUnit XML) and exits 0 iff all three observables match. This
test mirrors that script with a pure-Python model so the property can be
verified with thousands of synthetic replay-summary pairs without
shelling out to bash.

The model is intentionally minimal: a :class:`ReplaySummary` carries the
three observables the script compares, and :func:`idempotency_diff`
returns ``True`` when any of them disagree (i.e. mismatch detected,
matching the script's exit code 1).

Strategy:

* ``conclusion``: ``sampled_from(["success", "failure"])``.
* ``test_names``: ``sets`` of ``"<classname>::<name>"`` strings drawn
  from an alphanumeric alphabet. ``::`` is the separator that the
  ``extract_tests`` helper inside ``idempotency_diff.sh`` joins on, so
  test names contain alphanumerics plus ``::``.
* ``artifacts``: ``sets`` of file path strings (alphanumerics, ``/``,
  ``.``, ``-``, ``_``).

Two main properties:

* **Reflexivity / idempotency** -- for any single ``ReplaySummary s``,
  ``idempotency_diff(s, s)`` SHALL be ``False`` (no mismatch). This
  encodes "two replays with identical inputs produce no diff".
* **Sensitivity** -- for any ``ReplaySummary s`` and any single-field
  perturbation that changes the observable value of that field,
  ``idempotency_diff(s, s_perturbed)`` SHALL be ``True``. This encodes
  "perturbing any field produces a diff".

``max_examples=100`` per the task description.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from hypothesis import assume, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


Conclusion = Literal["success", "failure"]


@dataclass
class ReplaySummary:
    """Pure-Python mirror of the three observables compared by
    ``scripts/ci/idempotency_diff.sh``.

    * ``conclusion``: workflow conclusion token (``success`` or
      ``failure``), corresponding to ``conclusion.txt``.
    * ``test_names``: fully-qualified test names extracted from the
      JUnit XML report (``<classname>::<name>``). Order is irrelevant
      because the script compares sorted output, so a ``set`` is the
      natural representation.
    * ``artifacts``: artifact filenames listed in ``artifacts.txt``.
      Likewise an unordered set.
    """

    conclusion: Conclusion
    test_names: set[str] = field(default_factory=set)
    artifacts: set[str] = field(default_factory=set)


def idempotency_diff(a: ReplaySummary, b: ReplaySummary) -> bool:
    """Return ``True`` iff any observable differs between A and B.

    This mirrors the exit semantics of ``idempotency_diff.sh``:
    exit 0 (no mismatch) ↔ return ``False``; exit 1 (mismatch on
    conclusion / test_names / artifacts) ↔ return ``True``. The script
    short-circuits on the first disagreement; the model intentionally
    does not (it is a pure boolean), but the result is identical
    because the script reports any single mismatch as a failure.
    """
    if a.conclusion != b.conclusion:
        return True
    if a.test_names != b.test_names:
        return True
    if a.artifacts != b.artifacts:
        return True
    return False


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------


# Test names mirror the JUnit "<classname>::<name>" format produced by
# the script's ``extract_tests`` helper. Restrict the alphabet to
# alphanumerics so the strategy stays well-formed without needing a
# regex generator. Lengths are deliberately small to keep example
# generation fast.
_ALPHANUMERIC = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
    ),
    min_size=1,
    max_size=10,
)


def _fq_test_name() -> st.SearchStrategy[str]:
    return st.tuples(_ALPHANUMERIC, _ALPHANUMERIC).map(
        lambda parts: f"{parts[0]}::{parts[1]}"
    )


# Artifact filenames look like ``coverage.xml``,
# ``dist/admin-dashboard-1.0.tgz``, ``logs/build.txt``. Allow
# alphanumerics, ``/``, ``.``, ``-``, ``_``; require at least one char so
# the path is non-empty (matching how the script's ``artifacts.txt``
# records lines).
_ARTIFACT_PATH = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "/.-_"
    ),
    min_size=1,
    max_size=20,
)


_test_names_strategy = st.sets(_fq_test_name(), min_size=1, max_size=20)
_artifacts_strategy = st.sets(_ARTIFACT_PATH, min_size=1, max_size=10)
_conclusion_strategy = st.sampled_from(("success", "failure"))


@st.composite
def _replay_summaries(draw: st.DrawFn) -> ReplaySummary:
    return ReplaySummary(
        conclusion=draw(_conclusion_strategy),
        test_names=draw(_test_names_strategy),
        artifacts=draw(_artifacts_strategy),
    )


# Strategy for a perturbation: pick which field to change and draw a new
# value for it. We resolve the "must actually differ" constraint inside
# the test using ``assume`` so the strategy stays simple and shrinks well.
@st.composite
def _perturbations(draw: st.DrawFn) -> tuple[str, object]:
    field_name = draw(
        st.sampled_from(("conclusion", "test_names", "artifacts"))
    )
    if field_name == "conclusion":
        return field_name, draw(_conclusion_strategy)
    if field_name == "test_names":
        return field_name, draw(_test_names_strategy)
    return field_name, draw(_artifacts_strategy)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@given(summary=_replay_summaries())
@settings(max_examples=100)
def test_idempotency_no_diff_for_identical_inputs(
    summary: ReplaySummary,
) -> None:
    """**Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3**

    Two replays with identical inputs produce no diff. For every
    ``ReplaySummary s``, ``idempotency_diff(s, s)`` MUST be ``False``.
    This is the reflexivity half of Property 8: replaying the same
    workflow on the same commit, runner image, and lockfiles must agree
    with itself on conclusion, test name set, and artifact set.
    """
    assert idempotency_diff(summary, summary) is False, (
        "idempotency_diff reported a mismatch for two identical replay "
        "summaries; the diff must be False when inputs are equal.\n"
        f"  summary = {summary!r}"
    )


@given(summary=_replay_summaries(), perturbation=_perturbations())
@settings(max_examples=100)
def test_idempotency_sensitivity_to_field_perturbation(
    summary: ReplaySummary,
    perturbation: tuple[str, object],
) -> None:
    """**Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3**

    Perturbing any single observable field MUST produce a diff. For
    every ``ReplaySummary s`` and every value ``v`` that differs from
    ``getattr(s, field)``, ``idempotency_diff(s, replace(s, field=v))``
    MUST be ``True``. This is the sensitivity half of Property 8: a
    real change in conclusion, test names, or artifacts cannot be
    silently ignored by the diff.
    """
    field_name, new_value = perturbation
    original_value = getattr(summary, field_name)
    # Only consider perturbations that actually change the observable.
    # ``assume`` discards no-op draws (e.g. drawing the same conclusion
    # twice) without polluting the example database.
    assume(new_value != original_value)

    perturbed = replace(summary, **{field_name: new_value})

    assert idempotency_diff(summary, perturbed) is True, (
        "idempotency_diff failed to detect a single-field perturbation; "
        "any disagreement on conclusion / test_names / artifacts must "
        "produce a diff.\n"
        f"  field      = {field_name!r}\n"
        f"  original   = {original_value!r}\n"
        f"  perturbed  = {new_value!r}\n"
        f"  summary    = {summary!r}"
    )


@given(a=_replay_summaries(), b=_replay_summaries())
@settings(max_examples=100)
def test_idempotency_diff_is_symmetric(
    a: ReplaySummary, b: ReplaySummary
) -> None:
    """**Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3**

    The diff relation is symmetric: ``idempotency_diff(a, b)`` equals
    ``idempotency_diff(b, a)``. The script in ``ci-idempotency.yml``
    runs the diff with a fixed (A_DIR, B_DIR) ordering, but the
    underlying contract -- "two replays agree on three observables" --
    is order-independent, and the test name and artifact comparisons
    use set equality which is itself symmetric. This property guards
    against an accidental asymmetry leaking into the model (or into
    any future re-implementation of the script in Python).
    """
    assert idempotency_diff(a, b) == idempotency_diff(b, a), (
        "idempotency_diff is not symmetric.\n"
        f"  a = {a!r}\n"
        f"  b = {b!r}\n"
        f"  diff(a, b) = {idempotency_diff(a, b)!r}\n"
        f"  diff(b, a) = {idempotency_diff(b, a)!r}"
    )
