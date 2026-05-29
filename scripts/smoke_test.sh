#!/usr/bin/env bash
# scripts/smoke_test.sh — post-deploy smoke test (Requirement 18, design C12).
#
# Usage:
#   smoke_test.sh --frontend-url FURL --backend-url BURL --upstream-url UURL
#
# Issues three parallel HTTP probes (backend /healthz, frontend /, upstream
# /ok), each with a 5-second per-request timeout and an overall 30-second
# wall-clock budget. Exits 0 with no stdout when all three return 2xx in time;
# otherwise exits 1 and prints exactly one single-line `Structured_Error` JSON
# document to stdout that names the failed URL, the observed status (or one of
# the categorical sentinels `timeout`, `dns_error`, `tls_error`,
# `budget_exceeded`), and the elapsed time in milliseconds.
#
# Distinguished error codes (per Requirement 18 and design D1):
#   BAD_ARG, SMOKE_HTTP_FAIL, SMOKE_TIMEOUT, SMOKE_DNS_ERROR,
#   SMOKE_TLS_ERROR, SMOKE_BUDGET_EXCEEDED.
set -euo pipefail

# ---------------------------------------------------------------------------
# Identity & timestamps
# ---------------------------------------------------------------------------

if command -v uuidgen >/dev/null 2>&1; then
    REQUEST_ID=$(uuidgen 2>/dev/null | tr '[:upper:]' '[:lower:]')
fi
if [[ -z "${REQUEST_ID:-}" ]]; then
    # Fallback: high-resolution timestamp + PID. `date +%s%N` is GNU; fall back
    # to seconds when the platform lacks nanoseconds (BSD/macOS).
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

# Escape a string for inclusion as a JSON string value. Handles backslashes,
# double quotes, and the most common control characters. The smoke test never
# embeds attacker-controlled bodies into JSON — only the operator-supplied URL
# and short, fixed message strings — so this minimal escaper is sufficient.
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# emit_error <code> <message> [<url> <status> <elapsed_ms>]
# Prints exactly one single-line JSON Structured_Error to stdout. When the
# probe context fields (url/status/elapsed_ms) are omitted the document has
# only the four base fields required by D1.
emit_error() {
    local code="$1"
    local message="$2"
    local url="${3:-}"
    local status="${4:-}"
    local elapsed_ms="${5:-}"

    local ts
    ts=$(iso_timestamp)

    local em eu es
    em=$(json_escape "$message")
    eu=$(json_escape "$url")
    es=$(json_escape "$status")

    if [[ -n "$url" ]]; then
        # elapsed_ms is an integer; default to 0 if caller did not supply.
        local ems="${elapsed_ms:-0}"
        if ! [[ "$ems" =~ ^[0-9]+$ ]]; then
            ems=0
        fi
        printf '{"code":"%s","message":"%s","request_id":"%s","timestamp":"%s","url":"%s","status":"%s","elapsed_ms":%s}\n' \
            "$code" "$em" "$REQUEST_ID" "$ts" "$eu" "$es" "$ems"
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
# Argument parsing
# ---------------------------------------------------------------------------

FRONTEND_URL=""
BACKEND_URL=""
UPSTREAM_URL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --frontend-url)
            [[ $# -ge 2 ]] || bad_arg "Missing value for --frontend-url"
            FRONTEND_URL="$2"
            shift 2
            ;;
        --frontend-url=*)
            FRONTEND_URL="${1#--frontend-url=}"
            shift
            ;;
        --backend-url)
            [[ $# -ge 2 ]] || bad_arg "Missing value for --backend-url"
            BACKEND_URL="$2"
            shift 2
            ;;
        --backend-url=*)
            BACKEND_URL="${1#--backend-url=}"
            shift
            ;;
        --upstream-url)
            [[ $# -ge 2 ]] || bad_arg "Missing value for --upstream-url"
            UPSTREAM_URL="$2"
            shift 2
            ;;
        --upstream-url=*)
            UPSTREAM_URL="${1#--upstream-url=}"
            shift
            ;;
        *)
            bad_arg "Unrecognized argument: $1"
            ;;
    esac
done

[[ -n "$FRONTEND_URL" ]] || bad_arg "Missing required argument: --frontend-url"
[[ -n "$BACKEND_URL"  ]] || bad_arg "Missing required argument: --backend-url"
[[ -n "$UPSTREAM_URL" ]] || bad_arg "Missing required argument: --upstream-url"

# Compose probe URLs. Strip a single trailing slash so we always join exactly
# one. LangGraph exposes /ok as the stable public health endpoint.
B_PROBE="${BACKEND_URL%/}/healthz"
F_PROBE="${FRONTEND_URL%/}/"
U_PROBE="${UPSTREAM_URL%/}/ok"

# ---------------------------------------------------------------------------
# Probe execution
# ---------------------------------------------------------------------------

WORKDIR=$(mktemp -d 2>/dev/null || mktemp -d -t smoke_test)
cleanup() {
    rm -rf "$WORKDIR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Probe writer: writes "<http_code> <time_total>" to <label>.out and the
# curl exit code to <label>.exit. Runs under `set +e` so transient curl
# failures never abort the parent script via errexit.
run_probe() {
    local label="$1"
    local url="$2"
    local out="$WORKDIR/$label.out"
    local err="$WORKDIR/$label.err"
    local exitf="$WORKDIR/$label.exit"
    local rc

    set +e
    curl --max-time 5 \
         -o /dev/null \
         -s -S \
         -w '%{http_code} %{time_total}\n' \
         "$url" >"$out" 2>"$err"
    rc=$?
    set -e
    printf '%s' "$rc" >"$exitf"
}

START_SECONDS=$SECONDS

run_probe "backend"  "$B_PROBE"  &
PID_B=$!
run_probe "frontend" "$F_PROBE"  &
PID_F=$!
run_probe "upstream" "$U_PROBE"  &
PID_U=$!

# `wait` may return non-zero if a child exited non-zero; we already capture
# each probe's status to disk so we suppress those here.
wait "$PID_B" 2>/dev/null || true
wait "$PID_F" 2>/dev/null || true
wait "$PID_U" 2>/dev/null || true

ELAPSED_S=$(( SECONDS - START_SECONDS ))
ELAPSED_MS=$(( ELAPSED_S * 1000 ))

# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

# Wall-clock budget (R18.1). Per-probe timeouts are 5s, so an in-budget run
# with three parallel probes should finish in <=5s under nominal conditions.
if (( ELAPSED_S > 30 )); then
    emit_error "SMOKE_BUDGET_EXCEEDED" \
        "Total smoke test elapsed time exceeded 30s budget" \
        "" "budget_exceeded" "$ELAPSED_MS"
    exit 1
fi

# Convert curl's floating "%{time_total}" (seconds) to integer milliseconds.
to_ms() {
    local t="${1:-0}"
    awk -v v="$t" 'BEGIN { if (v == "" || v ~ /[^0-9.eE+\-]/) { printf "%d", 0 } else { printf "%d", v * 1000 } }'
}

# Inspect a single probe's recorded result. Echoes a single line on failure
# to stdout (the Structured_Error) and returns 1; returns 0 on success. We
# avoid `set -e` interactions by always returning explicitly.
process_probe() {
    local label="$1"
    local url="$2"
    local exit_code http_code time_total probe_ms body

    if [[ ! -f "$WORKDIR/$label.exit" ]]; then
        emit_error "SMOKE_HTTP_FAIL" \
            "Probe never produced a result" \
            "$url" "no_result" "0"
        return 1
    fi

    exit_code=$(cat "$WORKDIR/$label.exit")
    body=$(cat "$WORKDIR/$label.out" 2>/dev/null || true)
    http_code=$(printf '%s' "$body" | awk '{print $1}')
    time_total=$(printf '%s' "$body" | awk '{print $2}')
    probe_ms=$(to_ms "$time_total")

    case "$exit_code" in
        0)
            if [[ "$http_code" =~ ^[0-9]+$ ]] && \
               (( 10#$http_code >= 200 && 10#$http_code <= 299 )); then
                return 0
            fi
            emit_error "SMOKE_HTTP_FAIL" \
                "Probe returned non-2xx HTTP status" \
                "$url" "$http_code" "$probe_ms"
            return 1
            ;;
        28)
            emit_error "SMOKE_TIMEOUT" \
                "Probe exceeded the 5 second per-request timeout" \
                "$url" "timeout" "$probe_ms"
            return 1
            ;;
        6)
            emit_error "SMOKE_DNS_ERROR" \
                "Probe failed DNS resolution" \
                "$url" "dns_error" "$probe_ms"
            return 1
            ;;
        35|51|60)
            emit_error "SMOKE_TLS_ERROR" \
                "Probe failed TLS handshake" \
                "$url" "tls_error" "$probe_ms"
            return 1
            ;;
        *)
            # Treat any other non-zero curl exit as a generic HTTP failure
            # category; preserve the curl exit code in the status field so
            # operators can map back to libcurl's documented exit table.
            emit_error "SMOKE_HTTP_FAIL" \
                "Probe failed with curl exit code $exit_code" \
                "$url" "curl_exit_$exit_code" "$probe_ms"
            return 1
            ;;
    esac
}

# Process probes in a deterministic order so the "first-failing URL" choice
# is reproducible: backend → frontend → upstream.
if ! process_probe "backend"  "$B_PROBE";  then exit 1; fi
if ! process_probe "frontend" "$F_PROBE";  then exit 1; fi
if ! process_probe "upstream" "$U_PROBE";  then exit 1; fi

# All probes 2xx and total elapsed within budget — silent success per R18.1.
exit 0
