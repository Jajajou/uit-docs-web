"""Property-based test for the build reproducibility model.

Property 6: Build Reproducibility.

**Validates: Requirements 7.5, 19.1, 19.2, 19.3, 19.4**

Property 6 from the design document states:

    For any commit SHA ``c``, any image name ``I in {admin_backend,
    admin_frontend, lightrag}``, and any builder image version ``B``,
    two consecutive builds of ``I`` from ``c`` on ``B`` with identical
    build arguments and lockfiles SHALL produce manifest layer digests
    for the application-source layer and the dependency-install layer
    that are byte-for-byte identical.

This test exercises the *deterministic-build simulator*
:func:`tests.cicd.build_model.simulate_layer_digest`, which mirrors the
BuildKit input set as a pure function of
``(commit_sha, builder_version, build_args, lockfiles,
source_date_epoch)``. The simulator captures the upstream inputs that,
when held constant, BuildKit hashes into stable layer digests;
perturbing any of them must therefore force the digest to change. Two
complementary sub-properties encode this:

1. **Determinism**: identical inputs yield identical digests across
   two consecutive calls, even when the dict-typed inputs are
   constructed with different insertion orders (the simulator
   canonicalises them).
2. **Sensitivity**: a perturbation of any single input field —
   ``commit_sha``, ``builder_version``, any ``build_arg`` key/value,
   any ``lockfile`` key/value, or ``source_date_epoch`` — produces a
   *different* digest. Each perturbation strategy guarantees the new
   value is not equal to the original by construction, so the
   resulting digest inequality is a meaningful property of the
   simulator rather than a tautology.

Hypothesis strategies mirror the BuildKit input set:

* ``commit_sha``: 40-character lower-case hex strings.
* ``builder_version``: semver-like ``vMAJOR.MINOR.PATCH`` strings.
* ``build_args``: dictionaries with 1–5 entries, str→str.
* ``lockfiles``: dictionaries with 1–3 entries, file name → contents.
* ``source_date_epoch``: non-negative Unix epoch seconds bounded to a
  realistic range (year 2000 through year 2100).

Both properties run with ``max_examples=100`` per the task description.
"""

from __future__ import annotations

import string
from typing import Mapping

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.cicd.build_model import simulate_layer_digest


# ---------------------------------------------------------------------------
# Hypothesis strategies — mirror the BuildKit input space
# ---------------------------------------------------------------------------


# 16 distinct lower-case hex digits.
_HEX_LOWER = "0123456789abcdef"

_COMMIT_SHA = st.text(alphabet=_HEX_LOWER, min_size=40, max_size=40)


@st.composite
def _semver(draw: st.DrawFn) -> str:
    """Generate a ``vMAJOR.MINOR.PATCH`` builder version string."""
    major = draw(st.integers(min_value=0, max_value=99))
    minor = draw(st.integers(min_value=0, max_value=99))
    patch = draw(st.integers(min_value=0, max_value=99))
    return f"v{major}.{minor}.{patch}"


_BUILDER_VERSION = _semver()

# Restrict dict keys/values to printable ASCII so failure messages stay
# readable; the simulator does not depend on character set, but a
# tighter alphabet keeps Hypothesis shrinking effective.
_PRINTABLE = string.ascii_letters + string.digits + "._-"

_BUILD_ARGS = st.dictionaries(
    keys=st.text(alphabet=_PRINTABLE, min_size=1, max_size=20),
    values=st.text(alphabet=_PRINTABLE, max_size=50),
    min_size=1,
    max_size=5,
)

_LOCKFILES = st.dictionaries(
    keys=st.text(alphabet=_PRINTABLE, min_size=1, max_size=20),
    values=st.text(alphabet=_PRINTABLE, max_size=200),
    min_size=1,
    max_size=3,
)

# ``SOURCE_DATE_EPOCH`` in seconds; bounded to a realistic CI range
# (2000-01-01 through 2100-01-01) so values look like real timestamps
# while still spanning a wide perturbation space.
_SOURCE_DATE_EPOCH = st.integers(min_value=946_684_800, max_value=4_102_444_800)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reorder_dict(d: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of ``d`` with insertion order reversed.

    Used to confirm that the simulator's canonicalisation is order-
    independent. Returns a plain ``dict`` so that the comparison with
    the original is purely value-based.
    """
    return {k: d[k] for k in reversed(list(d.keys()))}


def _perturb_string(value: str, alphabet: str) -> str:
    """Return a string strictly different from ``value``."""
    if not value:
        return alphabet[0]
    last = value[-1]
    pick = next((c for c in alphabet if c != last), alphabet[0])
    return value + pick


def _perturb_dict_value(d: Mapping[str, str]) -> dict[str, str]:
    """Return a dict that differs from ``d`` in exactly one value.

    The strategies guarantee ``d`` is non-empty, so an arbitrary
    existing key's value is perturbed via :func:`_perturb_string`.
    """
    out = dict(d)
    key = next(iter(out))
    out[key] = _perturb_string(out[key], "abcXYZ123")
    return out


def _perturb_dict_key(d: Mapping[str, str]) -> dict[str, str]:
    """Return a dict that differs from ``d`` in exactly one key.

    Renames an arbitrary existing key to a guaranteed-fresh name. This
    exercises the ``key/value`` half of the sensitivity property —
    changing a key alone (with the same value) must change the digest.
    """
    out = dict(d)
    old_key = next(iter(out))
    new_key = _perturb_string(old_key, "abcXYZ123")
    # Defensive guard: if the perturbed name happens to collide with
    # an existing key, fall back to a sentinel that cannot collide
    # because of its leading double underscore prefix.
    if new_key in out:
        new_key = "__perturb_key__"
        while new_key in out:
            new_key += "_"
    out[new_key] = out.pop(old_key)
    return out


# ---------------------------------------------------------------------------
# Property 6.1 — determinism
# ---------------------------------------------------------------------------


@given(
    commit_sha=_COMMIT_SHA,
    builder_version=_BUILDER_VERSION,
    build_args=_BUILD_ARGS,
    lockfiles=_LOCKFILES,
    source_date_epoch=_SOURCE_DATE_EPOCH,
)
@settings(max_examples=100)
def test_identical_inputs_yield_identical_digest(
    commit_sha: str,
    builder_version: str,
    build_args: dict[str, str],
    lockfiles: dict[str, str],
    source_date_epoch: int,
) -> None:
    """**Validates: Requirements 7.5, 19.1, 19.2, 19.3, 19.4**

    Determinism sub-property of Property 6: two invocations with the
    same logical inputs return the same digest. The second invocation
    uses ``dict`` copies whose insertion order is reversed, exercising
    the simulator's canonicalisation guarantee that key order does not
    affect the digest.
    """
    first = simulate_layer_digest(
        commit_sha, builder_version, build_args, lockfiles, source_date_epoch
    )
    second = simulate_layer_digest(
        commit_sha,
        builder_version,
        _reorder_dict(build_args),
        _reorder_dict(lockfiles),
        source_date_epoch,
    )

    assert first == second, (
        "simulate_layer_digest is not deterministic under reordered dict "
        "inputs.\n"
        f"  first  = {first}\n"
        f"  second = {second}\n"
        f"  commit_sha = {commit_sha!r}\n"
        f"  builder_version = {builder_version!r}\n"
        f"  build_args (orig) = {build_args!r}\n"
        f"  lockfiles  (orig) = {lockfiles!r}\n"
        f"  source_date_epoch = {source_date_epoch}"
    )


# ---------------------------------------------------------------------------
# Property 6.2 — single-field sensitivity
# ---------------------------------------------------------------------------


_FIELDS = st.sampled_from(
    (
        "commit_sha",
        "builder_version",
        "build_args_value",
        "build_args_key",
        "lockfiles_value",
        "lockfiles_key",
        "source_date_epoch",
    )
)


@given(
    commit_sha=_COMMIT_SHA,
    builder_version=_BUILDER_VERSION,
    build_args=_BUILD_ARGS,
    lockfiles=_LOCKFILES,
    source_date_epoch=_SOURCE_DATE_EPOCH,
    field=_FIELDS,
)
@settings(max_examples=100)
def test_single_field_perturbation_changes_digest(
    commit_sha: str,
    builder_version: str,
    build_args: dict[str, str],
    lockfiles: dict[str, str],
    source_date_epoch: int,
    field: str,
) -> None:
    """**Validates: Requirements 7.5, 19.1, 19.2, 19.3, 19.4**

    Sensitivity sub-property of Property 6: perturbing exactly one of
    the input fields, leaving the others equal, must produce a
    different digest. Coverage includes ``commit_sha``,
    ``builder_version``, an arbitrary ``build_arg`` key *or* value,
    an arbitrary ``lockfile`` key *or* value, and
    ``source_date_epoch``. Each perturbation is constructed to be
    strictly different from the original, so the resulting inequality
    is a statement about the simulator's input sensitivity rather
    than a coincidence.
    """
    base = simulate_layer_digest(
        commit_sha, builder_version, build_args, lockfiles, source_date_epoch
    )

    if field == "commit_sha":
        perturbed_commit = _perturb_string(commit_sha, _HEX_LOWER)
        perturbed = simulate_layer_digest(
            perturbed_commit,
            builder_version,
            build_args,
            lockfiles,
            source_date_epoch,
        )
    elif field == "builder_version":
        # Append ``.1`` so the version string is guaranteed different
        # while remaining a plausibly-shaped version label.
        perturbed = simulate_layer_digest(
            commit_sha,
            builder_version + ".1",
            build_args,
            lockfiles,
            source_date_epoch,
        )
    elif field == "build_args_value":
        perturbed = simulate_layer_digest(
            commit_sha,
            builder_version,
            _perturb_dict_value(build_args),
            lockfiles,
            source_date_epoch,
        )
    elif field == "build_args_key":
        perturbed = simulate_layer_digest(
            commit_sha,
            builder_version,
            _perturb_dict_key(build_args),
            lockfiles,
            source_date_epoch,
        )
    elif field == "lockfiles_value":
        perturbed = simulate_layer_digest(
            commit_sha,
            builder_version,
            build_args,
            _perturb_dict_value(lockfiles),
            source_date_epoch,
        )
    elif field == "lockfiles_key":
        perturbed = simulate_layer_digest(
            commit_sha,
            builder_version,
            build_args,
            _perturb_dict_key(lockfiles),
            source_date_epoch,
        )
    else:  # field == "source_date_epoch"
        perturbed = simulate_layer_digest(
            commit_sha,
            builder_version,
            build_args,
            lockfiles,
            source_date_epoch + 1,
        )

    assert perturbed != base, (
        "Perturbing a single field did not change the digest.\n"
        f"  perturbed field = {field}\n"
        f"  base digest      = {base}\n"
        f"  perturbed digest = {perturbed}\n"
        f"  commit_sha = {commit_sha!r}\n"
        f"  builder_version = {builder_version!r}\n"
        f"  build_args = {build_args!r}\n"
        f"  lockfiles  = {lockfiles!r}\n"
        f"  source_date_epoch = {source_date_epoch}"
    )
