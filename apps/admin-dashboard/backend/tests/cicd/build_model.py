"""Pure deterministic-build simulator for the BuildKit input space.

This module realises a faithful, side-effect-free model of the inputs that
BuildKit consumes when producing a layer digest, as described by design
Property 6 (*Build Reproducibility*) of the
``cicd-deploy-admin-dashboard`` spec:

    For any commit SHA ``c``, any image name ``I in {admin_backend,
    admin_frontend, lightrag}``, and any builder image version ``B``,
    two consecutive builds of ``I`` from ``c`` on ``B`` with identical
    build arguments and lockfiles SHALL produce manifest layer digests
    for the application-source layer and the dependency-install layer
    that are byte-for-byte identical.

The real BuildKit pipeline obviously involves filesystem I/O and a
container runtime; the *property* we want to lock in, however, lives at
a higher level of abstraction: a hash function over the build's input
set must be (a) idempotent — identical inputs yield identical digests —
and (b) sensitive — perturbing any single input field changes the
digest. Both properties are necessary preconditions for byte-identical
layer digests, and both are testable without touching Docker.

:func:`simulate_layer_digest` is therefore implemented as a deterministic
SHA-256 over a canonical JSON serialisation of the five-tuple
``(commit_sha, builder_version, build_args, lockfiles, source_date_epoch)``.
``source_date_epoch`` is part of the BuildKit reproducibility contract
because it pins file mtimes that flow into layer hashes; including it
in the simulated input set keeps the model faithful to the real
BuildKit input set (Requirements 7.5 and 19.1 – 19.4).

Canonicalisation guarantees:

* dict keys are sorted lexicographically (``sort_keys=True``), so two
  dicts with the same key/value mapping but different insertion order
  serialise identically;
* there is no incidental whitespace
  (``separators=(",", ":")``);
* no ASCII escaping for non-ASCII characters
  (``ensure_ascii=False``), so the canonical form is unique up to
  Unicode normalisation of the inputs themselves.

Together these encode the BuildKit input set captured by
Requirements 7.5 and 19.1 – 19.4: the same source revision built on the
same builder image with the same args, lockfiles, and
``SOURCE_DATE_EPOCH`` produces the same digest, and any change to any
of those five inputs forces the digest to change.
"""

from __future__ import annotations

import hashlib
import json
from typing import Mapping


def simulate_layer_digest(
    commit_sha: str,
    builder_version: str,
    build_args: Mapping[str, str],
    lockfiles: Mapping[str, str],
    source_date_epoch: int,
) -> str:
    """Return a deterministic synthetic layer digest for the inputs.

    The digest is the lower-case hexadecimal SHA-256 of the canonical
    JSON serialisation of ``(commit_sha, builder_version, build_args,
    lockfiles, source_date_epoch)``. The serialisation sorts dict
    keys, omits incidental whitespace, and preserves non-ASCII
    characters verbatim, so:

    * Two calls with equal-valued inputs return the same digest, even
      when ``build_args`` or ``lockfiles`` were constructed with
      different insertion orders.
    * Changing any single field — including a single byte in any
      single dict key or value, or a single second of
      ``source_date_epoch`` — changes the digest, because SHA-256 is
      collision-resistant on the resulting distinct byte strings.

    Args:
        commit_sha: Source commit identifier (typically a 40-char
            lower-case hex string, but the function does not enforce
            length: any string is hashed verbatim).
        builder_version: BuildKit / builder image version tag.
        build_args: Mapping of ``--build-arg`` names to values.
        lockfiles: Mapping of lockfile name to lockfile contents.
        source_date_epoch: ``SOURCE_DATE_EPOCH`` value (Unix seconds)
            pinned for the build, mirroring the BuildKit
            reproducibility contract.

    Returns:
        The 64-character lower-case hex SHA-256 digest of the canonical
        JSON encoding of the inputs.
    """
    payload = {
        "commit_sha": commit_sha,
        "builder_version": builder_version,
        "build_args": dict(build_args),
        "lockfiles": dict(lockfiles),
        "source_date_epoch": int(source_date_epoch),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Backwards-compatible alias retained for any callers that imported the
# earlier four-argument name. New code should use
# :func:`simulate_layer_digest` directly.
def simulate_build_digest(
    commit_sha: str,
    builder_version: str,
    build_args: Mapping[str, str],
    lockfiles: Mapping[str, str],
    source_date_epoch: int = 0,
) -> str:
    return simulate_layer_digest(
        commit_sha, builder_version, build_args, lockfiles, source_date_epoch
    )


__all__ = ["simulate_layer_digest", "simulate_build_digest"]
