#!/usr/bin/env bash
set -euo pipefail

# scripts/supervisor_watchdog.sh
#
# Host-side restart-loop watchdog for the docker-compose supervisor.
# Implements the canonical algorithm documented in design.md section
# C11 ("Restart-loop backoff (R16.8)"):
#
#   For each service declared in the compose file, count `restart`
#   and `health_status: unhealthy` container events emitted by the
#   Docker daemon over a rolling WINDOW (default 60s). When the count
#   for a service reaches RESTART_THRESHOLD (5), stop the service via
#   `docker compose stop`, sleep `min(MAX_DELAY, BASE_DELAY * 2^(n-5))`
#   seconds, then start it again with `docker compose start`.
#
# The script performs exactly one pass and exits cleanly. It is meant
# to be invoked every 30 seconds by the systemd timer
# `uit-supervisor-watchdog.timer` (see deploy/systemd/).
#
# Failures of individual stop/start/sleep steps are logged to stderr
# but do not abort the pass; the watchdog continues with the remaining
# services so that one stuck container cannot suppress recovery for
# the rest of the stack.

# ---- Defaults --------------------------------------------------------------

COMPOSE_FILE="/opt/uit/docker-compose.yml"
WINDOW=60
RESTART_THRESHOLD=5
BASE_DELAY=10
MAX_DELAY=120

# ---- Backoff helper --------------------------------------------------------
#
# The canonical formula `delay = min(MAX_DELAY, BASE_DELAY * 2^(n -
# RESTART_THRESHOLD))` is implemented in scripts/lib/compute_backoff.sh so
# that the property-based test (tests/scripts/test_watchdog_backoff.py) can
# source the same file and verify the function across random inputs without
# pulling in the watchdog's docker-events main loop.
#
# We resolve the path relative to this script so installations that copy the
# watchdog to /usr/local/bin (see deploy/systemd/uit-supervisor-watchdog.service)
# can place compute_backoff.sh alongside it.

_WATCHDOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_BACKOFF_LIB="${_WATCHDOG_DIR}/lib/compute_backoff.sh"
if [[ ! -f "$_BACKOFF_LIB" ]]; then
  printf 'error: required library missing: %s\n' "$_BACKOFF_LIB" >&2
  exit 5
fi
# shellcheck source=lib/compute_backoff.sh
source "$_BACKOFF_LIB"

# ---- CLI parsing -----------------------------------------------------------

usage() {
  cat >&2 <<'USAGE'
Usage: supervisor_watchdog.sh [--compose-file PATH] [--window SECONDS]

Options:
  --compose-file PATH   Path to the production docker-compose file
                        (default: /opt/uit/docker-compose.yml)
  --window SECONDS      Rolling window for restart counting in seconds
                        (default: 60)
  -h, --help            Show this help text and exit
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-file)
      if [[ $# -lt 2 ]]; then
        printf 'error: --compose-file requires a value\n' >&2
        usage
        exit 2
      fi
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --window)
      if [[ $# -lt 2 ]]; then
        printf 'error: --window requires a value\n' >&2
        usage
        exit 2
      fi
      if ! [[ "$2" =~ ^[0-9]+$ ]] || [[ "$2" -le 0 ]]; then
        printf 'error: --window must be a positive integer (got %q)\n' "$2" >&2
        exit 2
      fi
      WINDOW="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      printf 'error: unknown argument %q\n' "$1" >&2
      usage
      exit 2
      ;;
  esac
done

# ---- Logging helpers -------------------------------------------------------

_iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log_info() {
  printf '%s component=supervisor_watchdog level=info %s\n' "$(_iso_now)" "$*"
}

log_err() {
  printf '%s component=supervisor_watchdog level=error %s\n' "$(_iso_now)" "$*" >&2
}

# ---- Preconditions ---------------------------------------------------------

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log_err "msg=\"required command not found\" command=$cmd"
    exit 3
  fi
}

require_command docker

if [[ ! -f "$COMPOSE_FILE" ]]; then
  log_err "msg=\"compose file missing\" path=$COMPOSE_FILE"
  exit 4
fi

# ---- Service discovery -----------------------------------------------------

list_services() {
  # `docker compose ps --services` lists every service declared in the
  # compose file regardless of whether the container is currently up.
  docker compose -f "$COMPOSE_FILE" ps --services 2>/dev/null || true
}

# ---- Event collection ------------------------------------------------------
#
# We pull the rolling window of container events in one call. Both
# `restart` and `health_status: unhealthy` events count toward the
# threshold per design C11. The output format is a single line per
# event with fields: <unix_time> <type> <action> <container_name>.

collect_events() {
  local since_arg="${WINDOW}s"
  docker events \
    --since "$since_arg" \
    --until "0s" \
    --format '{{.Time}} {{.Type}} {{.Action}} {{index .Actor.Attributes "name"}}' \
    2>/dev/null || true
}

# Count events that match a service. Compose-managed containers carry a
# `com.docker.compose.service` label equal to the service name, but the
# event format above only exposes the container name. Compose names
# containers as `<project>-<service>-<index>` (or `<project>_<service>_<index>`
# for legacy v1), so we match service names embedded in the container
# name with project- and index-agnostic patterns.

count_events_for_service() {
  local service="$1"
  local events="$2"
  if [[ -z "$events" ]]; then
    printf '0\n'
    return 0
  fi

  # Patterns: -<service>-<digits> (compose v2) or _<service>_<digits>
  # (legacy compose v1). Anchored at end of line.
  local pattern="[-_]${service}[-_][0-9]+$"

  printf '%s\n' "$events" \
    | awk -v pat="$pattern" '
        $2 == "container" && ($3 == "restart" || $3 == "health_status: unhealthy") {
          if (match($4, pat)) print
        }
      ' \
    | wc -l \
    | tr -d '[:space:]'
}

# ---- Per-service action ----------------------------------------------------

apply_backoff() {
  local service="$1"
  local count="$2"
  local delay
  delay="$(compute_backoff_delay "$count")"

  log_info "msg=\"restart loop detected\" service=$service count=$count window=${WINDOW}s delay=${delay}s action=stop"

  if ! docker compose -f "$COMPOSE_FILE" stop "$service"; then
    log_err "msg=\"docker compose stop failed\" service=$service"
    return 1
  fi

  if [[ "$delay" -gt 0 ]]; then
    log_info "msg=\"sleeping for backoff\" service=$service delay=${delay}s"
    if ! sleep "$delay"; then
      log_err "msg=\"sleep interrupted\" service=$service delay=${delay}s"
      # Fall through to restart anyway — leaving the service stopped
      # is worse than skipping the remaining wait.
    fi
  fi

  log_info "msg=\"resuming service\" service=$service action=start"
  if ! docker compose -f "$COMPOSE_FILE" start "$service"; then
    log_err "msg=\"docker compose start failed\" service=$service"
    return 1
  fi

  log_info "msg=\"backoff cycle complete\" service=$service count=$count delay=${delay}s"
  return 0
}

# ---- Main pass -------------------------------------------------------------

main() {
  log_info "msg=\"watchdog pass starting\" compose_file=$COMPOSE_FILE window=${WINDOW}s threshold=$RESTART_THRESHOLD"

  local services
  services="$(list_services)"
  if [[ -z "$services" ]]; then
    log_info "msg=\"no services declared in compose file; nothing to do\""
    return 0
  fi

  local events
  events="$(collect_events)"

  # Iterate services. We deliberately do not `set -e` around the loop
  # body so a failure on one service does not skip the rest.
  local service count
  while IFS= read -r service; do
    [[ -z "$service" ]] && continue
    count="$(count_events_for_service "$service" "$events")"
    if [[ "$count" -ge "$RESTART_THRESHOLD" ]]; then
      if ! apply_backoff "$service" "$count"; then
        log_err "msg=\"backoff cycle failed; continuing with remaining services\" service=$service"
      fi
    else
      log_info "msg=\"service healthy\" service=$service count=$count threshold=$RESTART_THRESHOLD"
    fi
  done <<<"$services"

  log_info "msg=\"watchdog pass complete\""
}

main "$@"
