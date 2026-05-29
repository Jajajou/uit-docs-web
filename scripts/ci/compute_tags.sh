#!/usr/bin/env bash
# scripts/ci/compute_tags.sh
#
# GHCR image-tag computation for the admin-dashboard docker-build-publish
# workflow (Requirements 7.1, 7.2; design Property 12).
#
# Given a workflow event kind and a single ref-or-SHA argument, prints the
# exact set of GHCR tag suffixes (one per line, on stdout) that the
# Docker_Build_Workflow MUST push for that event:
#
#   event_kind = push:main    arg = <commit SHA>
#                             -> prints "main" and "sha-<sha>"
#                                (i.e. the set { "main", "sha-" + sha })
#
#   event_kind = push:tag     arg = <ref name>
#                             -> if the ref matches "v*", prints "<ref>"
#                                and "latest" (i.e. { ref, "latest" })
#                             -> otherwise prints nothing and exits 0
#                                (Property 12 only defines the tag set
#                                 for tags matching v*; non-v* tags are
#                                 outside the publish contract)
#
# Output format: one tag suffix per line on stdout, no leading or trailing
# whitespace. The output is intended to be passed verbatim to the `tags:`
# input of `docker/build-push-action@v5` (which accepts a newline-separated
# list), with the caller prepending the image reference per matrix slot.
#
# Usage:
#   scripts/ci/compute_tags.sh <event-kind> <ref-or-sha>
#
#   event-kind   "push:main" or "push:tag"
#   ref-or-sha   For push:main: the commit SHA (used to build "sha-<sha>").
#                For push:tag:  the GitHub ref_name (e.g. "v1.2.3").
#
# Wiring into .github/workflows/docker-build-publish.yml (task 6.1):
#
#   - name: Compute image tags
#     id: tags
#     env:
#       GITHUB_REF: ${{ github.ref }}
#       GITHUB_REF_NAME: ${{ github.ref_name }}
#       GITHUB_SHA: ${{ github.sha }}
#       GITHUB_EVENT_NAME: ${{ github.event_name }}
#       IMAGE_REF: ${{ steps.build_meta.outputs.image_ref }}
#     run: |
#       set -euo pipefail
#       if [[ "$GITHUB_EVENT_NAME" == "push" && "$GITHUB_REF" == "refs/heads/main" ]]; then
#         suffixes="$(scripts/ci/compute_tags.sh push:main "$GITHUB_SHA")"
#       elif [[ "$GITHUB_EVENT_NAME" == "push" && "$GITHUB_REF" =~ ^refs/tags/ ]]; then
#         suffixes="$(scripts/ci/compute_tags.sh push:tag "$GITHUB_REF_NAME")"
#       else
#         echo "Unsupported event for docker-build-publish" >&2; exit 1
#       fi
#       {
#         echo 'tags<<__EOF__'
#         while IFS= read -r suffix; do
#           [[ -z "$suffix" ]] && continue
#           printf '%s:%s\n' "$IMAGE_REF" "$suffix"
#         done <<< "$suffixes"
#         echo '__EOF__'
#       } >> "$GITHUB_OUTPUT"
#
#   - uses: docker/build-push-action@v5
#     with:
#       tags: ${{ steps.tags.outputs.tags }}
#       # ... rest of build/push inputs ...
#
# Exit codes:
#   0   Tag set printed to stdout (possibly empty for push:tag refs that do
#       not match v*).
#   1   Wrong number of arguments, unknown event-kind, or empty ref-or-sha
#       for push:main. A usage message is written to stderr.

set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage: compute_tags.sh <event-kind> <ref-or-sha>

  event-kind   "push:main" or "push:tag"
  ref-or-sha   For push:main: the commit SHA (used to build "sha-<sha>").
               For push:tag:  the GitHub ref_name (e.g. "v1.2.3").

Prints the GHCR tag suffixes for the event, one per line, on stdout.
USAGE
}

if [[ $# -ne 2 ]]; then
  usage
  exit 1
fi

event_kind="$1"
ref_or_sha="$2"

case "$event_kind" in
  push:main)
    if [[ -z "$ref_or_sha" ]]; then
      printf 'compute_tags: empty SHA for push:main\n' >&2
      exit 1
    fi
    printf 'main\n'
    printf 'sha-%s\n' "$ref_or_sha"
    ;;
  push:tag)
    # Property 12 only defines the tag set for refs matching v*.
    # Any other ref name produces an empty tag set (no output, exit 0).
    case "$ref_or_sha" in
      v*)
        printf '%s\n' "$ref_or_sha"
        printf 'latest\n'
        ;;
      *)
        : # intentional: empty output for non-v* tags
        ;;
    esac
    ;;
  *)
    printf 'compute_tags: unknown event-kind: %s\n' "$event_kind" >&2
    usage
    exit 1
    ;;
esac
