#!/usr/bin/env bash
# scripts/deploy/ssh_deploy.sh — SSH-based docker-compose deploy step
# (Requirements 9.2, 9.3, 10.5, 10.6, 13.4; design C8/C9/D3).
#
# Reads required environment variables and runs a single SSH session against
# the target host that performs the deploy in order:
#
#   1. Read /etc/uit-docs/deployment.json (D3) if present and capture
#      `previous_image_tag` and `previous_alembic_revision` so they can be
#      recorded alongside the new manifest values. Uses `jq` when available;
#      falls back to `python3` so the script does not require jq on the
#      host. Missing manifest is treated as empty previous values (e.g.
#      first deploy).
#   2. Update /opt/uit/.env: strip any prior `IMAGE_TAG=` line and append a
#      fresh `IMAGE_TAG=<new>` line atomically; chmod 600.
#   3. `docker compose --env-file /opt/uit/.env -f $COMPOSE_FILE_PATH pull`
#   4. `docker compose --env-file /opt/uit/.env -f $COMPOSE_FILE_PATH up -d`
#   5. Best-effort capture of the now-current Alembic revision via
#      `docker compose ... exec -T admin_backend alembic current`. A failure
#      to read the revision (container not yet ready, alembic absent) is
#      recorded as the empty string and does not abort the deploy — the
#      deploy itself succeeded.
#   6. Atomically write /etc/uit-docs/deployment.json (D3 schema) with the
#      five fields `image_tag`, `previous_image_tag`, `alembic_revision`,
#      `previous_alembic_revision`, `deployed_at` (UTC ISO 8601). The file
#      is staged to a sibling .tmp path, then `mv`d into place to avoid
#      torn reads by `rollback.sh`.
#
# On any step failure the script prints exactly one single-line
# `Structured_Error` JSON document to stdout and exits non-zero. The codes
# emitted are:
#
#   BAD_ARG                  — missing or invalid required environment variable
#   DEPLOY_ENV_FAILED        — step 2 (.env update) failed on the host
#   DEPLOY_PULL_FAILED       — step 3 (`docker compose pull`) failed
#   DEPLOY_UP_FAILED         — step 4 (`docker compose up -d`) failed
#   DEPLOY_MANIFEST_FAILED   — step 1 (manifest read) or step 6 (manifest write) failed
#   DEPLOY_SSH_FAILED        — ssh transport itself failed before the remote
#                              deploy script could emit its own envelope
#
# `BAD_ARG` is part of the closed Structured_Error set in design D1. The
# `DEPLOY_*` codes are operator-facing extensions of that set introduced by
# this deploy script (and the parallel `rollback.sh`); the set extension is
# documented in `docs/runbooks/admin-dashboard.md` under "Operator
# Commands". They are intentionally distinct so an on-call engineer can
# tell at a glance which deploy phase failed without parsing the message
# field.

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

readonly REMOTE_ENV_PATH="/opt/uit/.env"
readonly REMOTE_MANIFEST_DIR="/etc/uit-docs"
readonly REMOTE_MANIFEST_PATH="/etc/uit-docs/deployment.json"
readonly REMOTE_BACKEND_SERVICE="admin_backend"

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
# JSON helpers
# ---------------------------------------------------------------------------

# Escape a string for embedding as a JSON string value. Inputs are either
# operator-supplied env vars (validated against a strict charset for
# IMAGE_TAG, opaque for SSH_USER/SSH_HOST) or output captured from trusted
# remote commands.
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# emit_error <code> <message> [<step> [<detail>]]
# Prints exactly one single-line Structured_Error JSON document to stdout
# per design D1. The optional `step` and `detail` fields make it easy for
# the deploy workflow's notification step to identify the failing phase.
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
: "${IMAGE_TAG:=}"
: "${COMPOSE_FILE_PATH:=}"

[[ -n "$SSH_HOST"             ]] || bad_arg "Missing required environment variable: SSH_HOST"
[[ -n "$SSH_USER"             ]] || bad_arg "Missing required environment variable: SSH_USER"
[[ -n "$SSH_PRIVATE_KEY_PATH" ]] || bad_arg "Missing required environment variable: SSH_PRIVATE_KEY_PATH"
[[ -n "$IMAGE_TAG"            ]] || bad_arg "Missing required environment variable: IMAGE_TAG"
[[ -n "$COMPOSE_FILE_PATH"    ]] || bad_arg "Missing required environment variable: COMPOSE_FILE_PATH"

[[ -f "$SSH_PRIVATE_KEY_PATH" ]] || bad_arg "SSH_PRIVATE_KEY_PATH does not point to a regular file: ${SSH_PRIVATE_KEY_PATH}"

# IMAGE_TAG length 1..128 mirrors the workflow_dispatch input bound in R10.1.
if (( ${#IMAGE_TAG} < 1 || ${#IMAGE_TAG} > 128 )); then
    bad_arg "IMAGE_TAG length must be between 1 and 128 characters (got ${#IMAGE_TAG})"
fi

# Restrict IMAGE_TAG to the OCI tag charset so we can splice it into the
# remote .env file and JSON manifest without further quoting. This is also
# the alphabet GHCR accepts.
if [[ ! "$IMAGE_TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
    bad_arg "IMAGE_TAG contains invalid characters; allowed: [A-Za-z0-9._-]"
fi

# ---------------------------------------------------------------------------
# Remote deploy (single SSH heredoc)
# ---------------------------------------------------------------------------

# All deploy steps run inside one ssh invocation. The remote script writes
# its own single-line Structured_Error to stdout on failure and exits
# non-zero, so the local wrapper just propagates whatever it produced.
#
# Positional args passed to the remote `bash -s --` (in order):
#   $1  IMAGE_TAG               — new tag to deploy (validated above)
#   $2  COMPOSE_FILE_PATH       — absolute path to docker-compose.yml on host
#   $3  REMOTE_ENV_PATH         — /opt/uit/.env
#   $4  REMOTE_MANIFEST_DIR     — /etc/uit-docs
#   $5  REMOTE_MANIFEST_PATH    — /etc/uit-docs/deployment.json
#   $6  REMOTE_BACKEND_SERVICE  — compose service name running alembic
#   $7  REQUEST_ID              — correlation id reused in remote envelopes

set +e
ssh_output=$(
    ssh \
        -i "$SSH_PRIVATE_KEY_PATH" \
        -o StrictHostKeyChecking=accept-new \
        -o BatchMode=yes \
        -o ConnectTimeout=15 \
        "${SSH_USER}@${SSH_HOST}" \
        bash -s -- \
            "$IMAGE_TAG" \
            "$COMPOSE_FILE_PATH" \
            "$REMOTE_ENV_PATH" \
            "$REMOTE_MANIFEST_DIR" \
            "$REMOTE_MANIFEST_PATH" \
            "$REMOTE_BACKEND_SERVICE" \
            "$REQUEST_ID" \
        <<'REMOTE_SCRIPT'
set -euo pipefail

image_tag="$1"
compose_file="$2"
env_path="$3"
manifest_dir="$4"
manifest_path="$5"
backend_service="$6"
request_id="$7"

iso_ts() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }

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

# -------------------------------------------------------------------------
# Step 1: read previous deployment manifest (if any)
# -------------------------------------------------------------------------
#
# Missing file is fine (first deploy). An unreadable or unparseable file
# IS an error — we cannot safely record `previous_*` values otherwise.

previous_image_tag=""
previous_alembic_revision=""

if [[ -e "$manifest_path" ]]; then
    if [[ ! -r "$manifest_path" ]]; then
        fail "DEPLOY_MANIFEST_FAILED" \
             "Existing deployment manifest is not readable" \
             "read_manifest" \
             "$manifest_path"
    fi

    if ! manifest_contents=$(cat "$manifest_path" 2>/dev/null); then
        fail "DEPLOY_MANIFEST_FAILED" \
             "Failed to read existing deployment manifest" \
             "read_manifest" \
             "$manifest_path"
    fi

    extract_field() {
        local field="$1"
        if command -v jq >/dev/null 2>&1; then
            printf '%s' "$manifest_contents" \
                | jq -r --arg f "$field" '.[$f] // ""' 2>/dev/null
            return $?
        fi
        if command -v python3 >/dev/null 2>&1; then
            printf '%s' "$manifest_contents" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(2)
val = data.get(sys.argv[1], "")
if val is None:
    val = ""
sys.stdout.write(str(val))
' "$field"
            return $?
        fi
        return 127
    }

    if ! previous_image_tag=$(extract_field "image_tag"); then
        fail "DEPLOY_MANIFEST_FAILED" \
             "Failed to parse existing deployment manifest" \
             "read_manifest" \
             "neither jq nor python3 is available, or manifest is not valid JSON"
    fi
    if ! previous_alembic_revision=$(extract_field "alembic_revision"); then
        fail "DEPLOY_MANIFEST_FAILED" \
             "Failed to parse existing deployment manifest" \
             "read_manifest" \
             "neither jq nor python3 is available, or manifest is not valid JSON"
    fi
fi

# -------------------------------------------------------------------------
# Step 2: update /opt/uit/.env with the new IMAGE_TAG (idempotent)
# -------------------------------------------------------------------------

env_dir=$(dirname "$env_path")
if ! mkdir -p "$env_dir"; then
    fail "DEPLOY_ENV_FAILED" \
         "Failed to create env directory" \
         "write_env" \
         "$env_dir"
fi

env_tmp="${env_path}.deploy.$$"
trap 'rm -f "$env_tmp" 2>/dev/null || true' EXIT

# Build the new env file: strip any existing IMAGE_TAG line(s) and append a
# fresh assignment. Use a restrictive umask so the temp file is created
# 600 even before chmod.
if ! (
    umask 077
    {
        if [[ -f "$env_path" ]]; then
            grep -v -E '^[[:space:]]*IMAGE_TAG=' "$env_path" || true
        fi
        printf 'IMAGE_TAG=%s\n' "$image_tag"
    } >"$env_tmp"
); then
    fail "DEPLOY_ENV_FAILED" \
         "Failed to stage updated env file" \
         "write_env" \
         "$env_path"
fi

if ! chmod 600 "$env_tmp"; then
    fail "DEPLOY_ENV_FAILED" \
         "Failed to chmod 600 staged env file" \
         "write_env" \
         "$env_tmp"
fi

if ! mv "$env_tmp" "$env_path"; then
    fail "DEPLOY_ENV_FAILED" \
         "Failed to install updated env file" \
         "write_env" \
         "$env_path"
fi
trap - EXIT

if ! chmod 600 "$env_path"; then
    fail "DEPLOY_ENV_FAILED" \
         "Failed to chmod 600 env file" \
         "write_env" \
         "$env_path"
fi

# -------------------------------------------------------------------------
# Step 3: docker compose pull
# -------------------------------------------------------------------------

if ! docker compose --env-file "$env_path" -f "$compose_file" pull; then
    fail "DEPLOY_PULL_FAILED" \
         "docker compose pull failed for new image tag" \
         "compose_pull" \
         "$image_tag"
fi

# -------------------------------------------------------------------------
# Step 4: docker compose up -d
# -------------------------------------------------------------------------

if ! docker compose --env-file "$env_path" -f "$compose_file" up -d; then
    fail "DEPLOY_UP_FAILED" \
         "docker compose up -d failed for new image tag" \
         "compose_up" \
         "$image_tag"
fi

# -------------------------------------------------------------------------
# Step 5: best-effort capture of current Alembic revision
# -------------------------------------------------------------------------
#
# Failure here is intentionally non-fatal: the deploy itself succeeded, and
# the manifest will record an empty alembic_revision. `docker compose exec`
# returns non-zero when the container is not yet healthy or when alembic
# is absent, so we explicitly swallow that.

current_alembic_revision=""
if alembic_out=$(
    docker compose --env-file "$env_path" -f "$compose_file" \
        exec -T "$backend_service" \
        alembic current 2>/dev/null
); then
    current_alembic_revision=$(printf '%s' "$alembic_out" | head -n1 | awk '{print $1}')
    case "$current_alembic_revision" in
        ''|INFO*|Revision*) current_alembic_revision="" ;;
    esac
fi

# -------------------------------------------------------------------------
# Step 6: atomically write the new deployment manifest (D3)
# -------------------------------------------------------------------------

deployed_at=$(iso_ts)

if ! mkdir -p "$manifest_dir"; then
    fail "DEPLOY_MANIFEST_FAILED" \
         "Failed to create manifest directory" \
         "write_manifest" \
         "$manifest_dir"
fi

# Build the manifest using whichever JSON tool is available so embedded
# special characters in `previous_*` fields cannot corrupt the document.
build_manifest() {
    if command -v jq >/dev/null 2>&1; then
        jq -nc \
            --arg image_tag "$image_tag" \
            --arg previous_image_tag "$previous_image_tag" \
            --arg alembic_revision "$current_alembic_revision" \
            --arg previous_alembic_revision "$previous_alembic_revision" \
            --arg deployed_at "$deployed_at" \
            '{
                image_tag: $image_tag,
                previous_image_tag: $previous_image_tag,
                alembic_revision: $alembic_revision,
                previous_alembic_revision: $previous_alembic_revision,
                deployed_at: $deployed_at
            }'
        return $?
    fi
    if command -v python3 >/dev/null 2>&1; then
        IMAGE_TAG="$image_tag" \
        PREVIOUS_IMAGE_TAG="$previous_image_tag" \
        ALEMBIC_REVISION="$current_alembic_revision" \
        PREVIOUS_ALEMBIC_REVISION="$previous_alembic_revision" \
        DEPLOYED_AT="$deployed_at" \
        python3 -c '
import json, os, sys
doc = {
    "image_tag": os.environ["IMAGE_TAG"],
    "previous_image_tag": os.environ["PREVIOUS_IMAGE_TAG"],
    "alembic_revision": os.environ["ALEMBIC_REVISION"],
    "previous_alembic_revision": os.environ["PREVIOUS_ALEMBIC_REVISION"],
    "deployed_at": os.environ["DEPLOYED_AT"],
}
sys.stdout.write(json.dumps(doc, separators=(",", ":")))
'
        return $?
    fi
    return 127
}

manifest_tmp="${manifest_path}.deploy.$$"
trap 'rm -f "$manifest_tmp" 2>/dev/null || true' EXIT

if ! manifest_body=$(build_manifest); then
    fail "DEPLOY_MANIFEST_FAILED" \
         "Failed to build deployment manifest JSON" \
         "write_manifest" \
         "neither jq nor python3 is available"
fi

if ! printf '%s\n' "$manifest_body" >"$manifest_tmp"; then
    fail "DEPLOY_MANIFEST_FAILED" \
         "Failed to stage deployment manifest" \
         "write_manifest" \
         "$manifest_path"
fi

if ! chmod 644 "$manifest_tmp"; then
    fail "DEPLOY_MANIFEST_FAILED" \
         "Failed to chmod manifest temp file" \
         "write_manifest" \
         "$manifest_tmp"
fi

if ! mv "$manifest_tmp" "$manifest_path"; then
    fail "DEPLOY_MANIFEST_FAILED" \
         "Failed to install deployment manifest" \
         "write_manifest" \
         "$manifest_path"
fi
trap - EXIT

printf '[deploy] complete: image=%s previous=%s revision=%s previous_revision=%s\n' \
    "$image_tag" \
    "${previous_image_tag:-<none>}" \
    "${current_alembic_revision:-<none>}" \
    "${previous_alembic_revision:-<none>}" >&2

exit 0
REMOTE_SCRIPT
)
ssh_rc=$?
set -e

# Re-emit anything the remote script wrote (its Structured_Error on failure
# or status logs on success).
if [[ -n "$ssh_output" ]]; then
    printf '%s\n' "$ssh_output"
fi

if (( ssh_rc != 0 )); then
    # If the remote script never produced a Structured_Error envelope
    # (e.g. ssh transport failed before bash -s ran, or the remote shell
    # was killed before fail() could print) wrap the failure so the
    # operator always sees exactly one envelope on stdout.
    if ! grep -q '"code"[[:space:]]*:' <<<"$ssh_output"; then
        emit_error "DEPLOY_SSH_FAILED" \
                   "ssh transport or remote shell failed before deploy could run" \
                   "ssh_invoke" \
                   "exit_code=${ssh_rc}"
    fi
    exit 1
fi

exit 0
