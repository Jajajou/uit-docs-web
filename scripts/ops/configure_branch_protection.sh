#!/usr/bin/env bash
# scripts/ops/configure_branch_protection.sh
#
# Configures GitHub branch protection on `main` for the
# `cicd-deploy-admin-dashboard` repository (Requirements 2.7, 3.4, 4.4,
# 5.1, 5.2, 5.3, 5.4).
#
# Required status checks that must conclude `success` before a pull
# request can be merged:
#   * frontend-ci
#   * backend-ci
#   * langgraph-ci
#
# Additional protections:
#   * Pull-request reviews required (>=1 approval, dismiss stale reviews
#     on new commits).
#   * Conversation resolution required (no unresolved review comments).
#   * Strict status checks (the head ref must be up to date with `main`
#     before merging, so the required checks run on the merged result).
#   * No force pushes; no deletions; admins included.
#
# This script is idempotent: re-running it converges branch protection
# to the declared state. It is safe to run as part of repository
# bootstrap or after adding a new required check.
#
# Usage:
#   REPO=<owner>/<repo> scripts/ops/configure_branch_protection.sh
#   scripts/ops/configure_branch_protection.sh --repo <owner>/<repo>
#   scripts/ops/configure_branch_protection.sh --dry-run
#
# Environment / flags:
#   REPO         GitHub `<owner>/<repo>` slug. If unset, the script
#                derives it from `git remote get-url origin`.
#   BRANCH       Branch to protect. Defaults to `main`.
#   GH_TOKEN     Token consumed by `gh`. Must have `repo` scope (admin
#                permissions on the target repository) since branch
#                protection is an admin-only API.
#   --dry-run    Print the API request that would be made and exit 0
#                without calling GitHub.
#   --repo       Override REPO from the command line.
#   --branch     Override BRANCH from the command line.
#
# Dependencies:
#   * `gh` (GitHub CLI) authenticated against the target repository.
#   * `jq` for constructing the JSON request body.
#
# Exit codes:
#   0   Branch protection successfully applied (or dry-run printed).
#   1   Argument or environment error (missing REPO, unknown flag).
#   2   Required dependency missing (`gh` or `jq` not found).
#   3   GitHub API call failed (auth, permissions, or network).

set -euo pipefail

print_usage() {
  cat <<'USAGE'
Usage: configure_branch_protection.sh [--repo <owner>/<repo>] [--branch <name>] [--dry-run]

Applies GitHub branch protection to the target branch with required
status checks: frontend-ci, backend-ci, langgraph-ci.

Required environment:
  REPO       GitHub <owner>/<repo> slug (or use --repo).
  GH_TOKEN   Token with admin:repo permissions (consumed by gh).

Optional:
  BRANCH     Defaults to `main` (or use --branch).
USAGE
}

# --- Argument parsing ------------------------------------------------------

REPO="${REPO:-}"
BRANCH="${BRANCH:-main}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || { echo "configure_branch_protection: --repo requires a value" >&2; exit 1; }
      REPO="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || { echo "configure_branch_protection: --branch requires a value" >&2; exit 1; }
      BRANCH="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "configure_branch_protection: unknown argument: $1" >&2
      print_usage >&2
      exit 1
      ;;
  esac
done

# --- Dependency checks -----------------------------------------------------

for cmd in gh jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "configure_branch_protection: required dependency missing: $cmd" >&2
    exit 2
  fi
done

# --- Resolve REPO ----------------------------------------------------------

if [[ -z "$REPO" ]]; then
  if ! command -v git >/dev/null 2>&1; then
    echo "configure_branch_protection: REPO is unset and git is not available to derive it" >&2
    exit 1
  fi
  origin_url="$(git remote get-url origin 2>/dev/null || true)"
  if [[ -z "$origin_url" ]]; then
    echo "configure_branch_protection: REPO is unset and 'git remote get-url origin' produced no output" >&2
    exit 1
  fi
  # Match SSH (git@github.com:owner/repo.git) and HTTPS (https://github.com/owner/repo[.git]).
  if [[ "$origin_url" =~ github\.com[:/]([^/]+)/([^/.]+)(\.git)?/?$ ]]; then
    REPO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  else
    echo "configure_branch_protection: could not parse owner/repo from origin: $origin_url" >&2
    exit 1
  fi
fi

if [[ ! "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "configure_branch_protection: REPO is not in <owner>/<repo> form: $REPO" >&2
  exit 1
fi

# --- Build request body ----------------------------------------------------
#
# Reference:
#   https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection
#
# `required_status_checks.contexts` must list the exact GitHub Actions
# workflow names (the `name:` field of the workflow YAML, which we keep
# in sync with the filename via `tests/cicd/workflow_registry.py`).
#
# `strict: true` forces the head branch to be up-to-date with `main`
# before merging, which guarantees that the required CI runs against
# the post-merge tree.

required_contexts=(frontend-ci backend-ci langgraph-ci)

body="$(jq -n \
  --argjson contexts "$(printf '%s\n' "${required_contexts[@]}" | jq -R . | jq -s .)" \
  '{
    required_status_checks: {
      strict: true,
      contexts: $contexts
    },
    enforce_admins: true,
    required_pull_request_reviews: {
      dismiss_stale_reviews: true,
      require_code_owner_reviews: false,
      required_approving_review_count: 1,
      require_last_push_approval: false
    },
    restrictions: null,
    required_linear_history: false,
    allow_force_pushes: false,
    allow_deletions: false,
    block_creations: false,
    required_conversation_resolution: true,
    lock_branch: false,
    allow_fork_syncing: false
  }')"

api_path="repos/${REPO}/branches/${BRANCH}/protection"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'DRY RUN: gh api -X PUT %s --input -\n' "$api_path"
  printf 'Body:\n%s\n' "$body"
  exit 0
fi

# --- Apply -----------------------------------------------------------------

if ! printf '%s' "$body" | gh api \
      -X PUT \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "$api_path" \
      --input - >/dev/null; then
  echo "configure_branch_protection: gh api PUT $api_path failed" >&2
  exit 3
fi

printf 'Branch protection applied to %s on %s with required checks: %s\n' \
  "$REPO" "$BRANCH" "${required_contexts[*]}"
