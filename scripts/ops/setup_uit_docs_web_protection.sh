#!/usr/bin/env bash
# scripts/ops/setup_uit_docs_web_protection.sh
#
# Turnkey Phase 2 helper: protect `main` and `web_implement_split` on
# https://github.com/Jajajou/uit-docs-web with the same rule set:
#
#   - Required status checks (strict mode): frontend-ci, backend-ci, langgraph-ci
#   - Required PR reviews: 1 approving review, dismiss stale on new commits
#   - Required conversation resolution
#   - Enforce for admins
#   - No force pushes, no deletions
#
# REQUIRES:
#   * `gh` (GitHub CLI) authenticated as the *owner* of `Jajajou/uit-docs-web`
#     (Jajajou). The duckonthemic collaborator account does NOT have admin and
#     branch protection is admin-only.
#   * `jq` (or python3 fallback for JSON construction is optional — this script
#     ships the JSON inline so jq is NOT required).
#
# USAGE:
#   bash scripts/ops/setup_uit_docs_web_protection.sh
#
#   Or per-branch (default applies to both):
#   bash scripts/ops/setup_uit_docs_web_protection.sh main
#   bash scripts/ops/setup_uit_docs_web_protection.sh web_implement_split

set -euo pipefail

REPO="${REPO:-Jajajou/uit-docs-web}"
DEFAULT_BRANCHES=(main web_implement_split)

if [[ $# -gt 0 ]]; then
    BRANCHES=("$@")
else
    BRANCHES=("${DEFAULT_BRANCHES[@]}")
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "error: gh CLI not found on PATH" >&2
    exit 1
fi

# Verify the authenticated user has admin on the target repo. Without admin,
# the protection API will silently 404.
who="$(gh api user --jq '.login' 2>/dev/null || echo unknown)"
admin_flag="$(gh api "repos/${REPO}" --jq '.permissions.admin' 2>/dev/null || echo false)"
echo "Authenticated as: ${who}"
echo "Repository:       ${REPO}"
echo "Admin permission: ${admin_flag}"
if [[ "${admin_flag}" != "true" ]]; then
    cat >&2 <<EOF

ERROR: ${who} does not have admin permission on ${REPO}.

Branch protection is an admin-only API; without admin scope, the call returns
HTTP 404 (or HTTP 403 when authenticated by non-admin tokens). To proceed:

  1. Sign in as the repo owner (Jajajou) and re-run:
        gh auth login
        bash scripts/ops/setup_uit_docs_web_protection.sh

  2. Or apply protection through the GitHub web UI:
        https://github.com/${REPO}/settings/branches
     For each of: ${BRANCHES[*]}
       - Add rule -> branch name pattern (exact)
       - Require a pull request before merging (1 approval, dismiss stale)
       - Require status checks to pass before merging (strict)
            * frontend-ci
            * backend-ci
            * langgraph-ci
       - Require conversation resolution before merging
       - Do not allow bypassing the above settings

EOF
    exit 1
fi

# Inline JSON body — no jq required.
read -r -d '' BODY <<'JSON' || true
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "frontend-ci",
      "backend-ci",
      "langgraph-ci"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON

for BRANCH in "${BRANCHES[@]}"; do
    echo
    echo "==> protecting ${REPO}#${BRANCH} ..."
    if printf '%s' "$BODY" | gh api \
            -X PUT \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "repos/${REPO}/branches/${BRANCH}/protection" \
            --input - >/dev/null; then
        echo "    OK: applied"
    else
        echo "    FAILED — see error above" >&2
        exit 2
    fi
done

echo
echo "Done. Verify with:"
for BRANCH in "${BRANCHES[@]}"; do
    echo "  gh api repos/${REPO}/branches/${BRANCH}/protection --jq '.required_status_checks'"
done
