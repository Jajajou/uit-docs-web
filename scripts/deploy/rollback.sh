#!/usr/bin/env bash
# scripts/deploy/rollback.sh — Rollback_Procedure executor (Requirement 9.5,
# 11.5, 12.6, 12.8; design C8/C9/D3).
#
# Reads the host-side deployment manifest (/etc/uit-docs/deployment.json)
# written by ssh_deploy.sh on the most recent successful deploy, restores
# `previous_image_tag` into /opt/uit/.env, runs `docker compose pull` and
# `docker compose up -d` against the production Compose_File, and — when a
# previous Alembic revision is recorded — runs
# `alembic downgrade <previous_alembic_revision>` inside the admin_backend
# container. Any step failure halts the rollback and exits non-zero with a
# single-line `Structured_Error` JSON document on stdout (D1 envelope).
#
# Required environment variables (validated up front):
#   SSH_HOST              — production host (ssh target)
#   SSH_USER              — ssh login user
#   SSH_PRIVATE_KEY_PATH  — path to the ssh private key file
#   COMPOSE_FILE_PATH     — absolute path on the remote host to docker-compose.yml
#
# Exit codes:
#   0  rollback completed successfully
#   1  validation, manifest, deploy, or downgrade failure (see Structured_Error code)
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REMOTE_MANIFEST_PATH="/etc/uit-docs/deployment.json"
REMOTE_ENV_PATH="/opt/uit/.env"
REMOTE_BACKEND_SERVICE="admin_backend"

# ---------------------------------------------------------------------------
# Identity & timestamps
# ---------------------------------------------------------------------------

if command -v uuidgen >/dev/null 2>&1; then
    REQUEST_ID=$(uuidgen 2>/dev/null | tr '[:upper:]' '[:lower:]')
fi
if [[ -z "${REQUEST_ID:-}" ]]; then
    _ns=$(date +%s%N 2>/dev/null || true)
    if [[ -z "$_ns" || "$_ns" == *N ]]; then
        _ns=$(date +%s)
    fi
    REQUEST_ID="${_ns}-$$"
fi

iso_timestamp() {
    date -u +'%Y-%m-%dT%H:%M:%SZ'
}

# ---------------------------------------------------------------------------
# JSON helpers (minimal escaper — mirrors scripts/smoke_test.sh)
# ---------------------------------------------------------------------------

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# emit_error <code> <message> [<step>] [<detail>]
# Prints exactly one single-line Structured_Error JSON document to stdout.
emit_error() {
    local code="$1"
    local message="$2"
    local step="${3:-}"
    local detail="${4:-}"

    local ts em es ed
    ts=$(iso_timestamp)
    em=$(json_escape "$message")
    es=$(json_escape "$step")
    ed=$(json_escape "$detail")

    if [[ -n "$step" || -n "$detail" ]]; then
        printf '{"code":"%s","message":"%s","request_id":"%s","timestamp":"%s","step":"%s","detail":"%s"}\n' \
            "$code" "$em" "$REQUEST_ID" "$ts" "$es" "$ed"
    else
        printf '{"code":"%s","message":"%s","request_id":"%s","timestamp":"%s"}\n' \
            "$code" "$em" "$REQUEST_ID" "$ts"
    fi
}

bad_arg() {
    emit_error "BAD_ARG" "$1"
    exit 1
}

# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

: "${SSH_HOST:=}"
: "${SSH_USER:=}"
: "${SSH_PRIVATE_KEY_PATH:=}"
: "${COMPOSE_FILE_PATH:=}"

[[ -n "$SSH_HOST"             ]] || bad_arg "Missing required env var: SSH_HOST"
[[ -n "$SSH_USER"             ]] || bad_arg "Missing required env var: SSH_USER"
[[ -n "$SSH_PRIVATE_KEY_PATH" ]] || bad_arg "Missing required env var: SSH_PRIVATE_KEY_PATH"
[[ -n "$COMPOSE_FILE_PATH"    ]] || bad_arg "Missing required env var: COMPOSE_FILE_PATH"

if [[ ! -r "$SSH_PRIVATE_KEY_PATH" ]]; then
    bad_arg "SSH_PRIVATE_KEY_PATH is not readable: $SSH_PRIVATE_KEY_PATH"
fi

# ---------------------------------------------------------------------------
# Remote rollback (single SSH heredoc)
# ---------------------------------------------------------------------------

# The remote script is executed by `bash -s` over ssh. It writes its own
# Structured_Error to stdout on failure and exits non-zero so the local
# wrapper can propagate the operator-facing JSON unchanged.
#
# Variables interpolated from the local environment are quoted into the
# heredoc; everything else is escaped (`\$var`) so it is evaluated remotely.

set +e
ssh_output=$(
    ssh \
        -i "$SSH_PRIVATE_KEY_PATH" \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=15 \
        -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=4 \
        "${SSH_USER}@${SSH_HOST}" \
        bash -s -- \
            "$REMOTE_MANIFEST_PATH" \
            "$REMOTE_ENV_PATH" \
            "$COMPOSE_FILE_PATH" \
            "$REMOTE_BACKEND_SERVICE" \
            "$REQUEST_ID" \
        <<'REMOTE_SCRIPT'
set -euo pipefail

manifest_path="$1"
env_path="$2"
compose_file="$3"
backend_service="$4"
request_id="$5"

iso_ts() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }

# Minimal JSON-string escaper (mirrors the local helper).
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# emit_error <code> <message> <step> [<detail>]
emit_error() {
    local code="$1"
    local message="$2"
    local step="$3"
    local detail="${4:-}"
    local ts em es ed
    ts=$(iso_ts)
    em=$(json_escape "$message")
    es=$(json_escape "$step")
    ed=$(json_escape "$detail")
    printf '{"code":"%s","message":"%s","request_id":"%s","timestamp":"%s","step":"%s","detail":"%s"}\n' \
        "$code" "$em" "$request_id" "$ts" "$es" "$ed"
}

fail() {
    # fail <code> <message> <step> [<detail>]
    emit_error "$1" "$2" "$3" "${4:-}"
    exit 1
}

# Step 1: read the deployment manifest.
if [[ ! -f "$manifest_path" ]]; then
    fail "ROLLBACK_NO_MANIFEST" \
         "Deployment manifest not found; cannot determine rollback target" \
         "read_manifest" \
         "$manifest_path"
fi

if ! manifest_contents=$(cat "$manifest_path" 2>&1); then
    fail "ROLLBACK_NO_MANIFEST" \
         "Deployment manifest is unreadable" \
         "read_manifest" \
         "$manifest_path"
fi

# Step 2: extract previous_image_tag and previous_alembic_revision.
# Prefer jq when available; fall back to python3 for portability.
extract_field() {
    local field="$1"
    local value=""
    if command -v jq >/dev/null 2>&1; then
        # `// empty` collapses null/missing into the empty string.
        value=$(printf '%s' "$manifest_contents" \
                | jq -r --arg f "$field" '.[$f] // empty' 2>/dev/null) || value=""
    elif command -v python3 >/dev/null 2>&1; then
        value=$(printf '%s' "$manifest_contents" \
                | python3 -c 'import json,sys
try:
    data = json.load(sys.stdin)
    v = data.get(sys.argv[1], "")
    print(v if v is not None else "")
except Exception:
    sys.exit(2)
' "$field" 2>/dev/null) || value=""
    else
        return 2
    fi
    printf '%s' "$value"
}

if ! previous_image_tag=$(extract_field "previous_image_tag"); then
    fail "ROLLBACK_NO_TOOLS" \
         "Neither jq nor python3 is available to parse the deployment manifest" \
         "parse_manifest"
fi
if ! previous_alembic_revision=$(extract_field "previous_alembic_revision"); then
    fail "ROLLBACK_NO_TOOLS" \
         "Neither jq nor python3 is available to parse the deployment manifest" \
         "parse_manifest"
fi

if [[ -z "$previous_image_tag" ]]; then
    fail "ROLLBACK_NO_TARGET" \
         "previous_image_tag missing from deployment manifest; no rollback target available" \
         "validate_manifest" \
         "$manifest_path"
fi

printf '[rollback] target image tag: %s\n' "$previous_image_tag" >&2
if [[ -n "$previous_alembic_revision" ]]; then
    printf '[rollback] target alembic revision: %s\n' "$previous_alembic_revision" >&2
else
    printf '[rollback] no previous_alembic_revision recorded — skipping downgrade\n' >&2
fi

# Step 3: rewrite IMAGE_TAG in the .env file (chmod 600 to match ssh_deploy).
env_dir=$(dirname "$env_path")
if ! mkdir -p "$env_dir" 2>/dev/null; then
    fail "ROLLBACK_ENV_FAILED" \
         "Failed to create env directory" \
         "write_env" \
         "$env_dir"
fi

env_tmp="${env_path}.rollback.$$"
{
    if [[ -f "$env_path" ]]; then
        # Strip any existing IMAGE_TAG line to keep the file idempotent.
        grep -v -E '^[[:space:]]*IMAGE_TAG=' "$env_path" || true
    fi
    printf 'IMAGE_TAG=%s\n' "$previous_image_tag"
} > "$env_tmp" 2>/dev/null || fail \
    "ROLLBACK_ENV_FAILED" \
    "Failed to stage updated env file" \
    "write_env" \
    "$env_path"

if ! mv "$env_tmp" "$env_path"; then
    rm -f "$env_tmp" 2>/dev/null || true
    fail "ROLLBACK_ENV_FAILED" \
         "Failed to install updated env file" \
         "write_env" \
         "$env_path"
fi

if ! chmod 600 "$env_path"; then
    fail "ROLLBACK_ENV_FAILED" \
         "Failed to chmod 600 env file" \
         "write_env" \
         "$env_path"
fi

# Step 4: docker compose pull (uses IMAGE_TAG from the rewritten env file).
if ! docker compose --env-file "$env_path" -f "$compose_file" pull; then
    fail "ROLLBACK_PULL_FAILED" \
         "docker compose pull failed for previous image tag" \
         "compose_pull" \
         "$previous_image_tag"
fi

# Step 5: docker compose up -d.
if ! docker compose --env-file "$env_path" -f "$compose_file" up -d; then
    fail "ROLLBACK_UP_FAILED" \
         "docker compose up -d failed during rollback" \
         "compose_up" \
         "$previous_image_tag"
fi

# Step 6: alembic downgrade (only when a previous revision is recorded).
if [[ -n "$previous_alembic_revision" ]]; then
    if ! docker compose --env-file "$env_path" -f "$compose_file" \
            exec -T "$backend_service" \
            alembic downgrade "$previous_alembic_revision"; then
        # R12.8: halt the rollback and identify the failed downgrade revision.
        fail "ROLLBACK_DOWNGRADE_FAILED" \
             "alembic downgrade failed; database state retained" \
             "alembic_downgrade" \
             "$previous_alembic_revision"
    fi
fi

printf '[rollback] complete: image=%s revision=%s\n' \
    "$previous_image_tag" "${previous_alembic_revision:-<none>}" >&2
exit 0
REMOTE_SCRIPT
)
ssh_rc=$?
set -e

# Re-emit anything the remote script wrote (its own Structured_Error on
# failure, or status logs on success).
if [[ -n "$ssh_output" ]]; then
    printf '%s\n' "$ssh_output"
fi

if (( ssh_rc != 0 )); then
    # If the remote script never produced a Structured_Error (e.g. ssh itself
    # failed before bash -s ran), wrap the failure so the operator always sees
    # one envelope.
    if ! grep -q '"code"[[:space:]]*:' <<<"$ssh_output"; then
        emit_error "ROLLBACK_SSH_FAILED" \
                   "ssh transport or remote shell failed before rollback could run" \
                   "ssh_invoke" \
                   "exit_code=${ssh_rc}"
    fi
    exit 1
fi

exit 0
