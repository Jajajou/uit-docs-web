#!/usr/bin/env bash
# scripts/ci/alembic_round_trip.sh
#
# Alembic migration round-trip check for the admin-dashboard backend CI
# (Requirements 12.1, 12.2, 12.3, 12.4).
#
# Against an ephemeral SQLite database stored in a temporary file under
# ${RUNNER_TEMP:-/tmp}, this script runs:
#
#   1. timeout 300 alembic upgrade head
#   2. timeout 300 alembic downgrade base
#   3. timeout 300 alembic upgrade head
#
# Each command's exit code is captured in `$?` immediately after it runs and
# inspected explicitly. Any non-zero exit (including the 124 emitted by
# `timeout(1)` when the 300-second wall-clock budget is exhausted) causes the
# script to abort with an error message identifying the failed step and to
# propagate a non-zero exit. The temporary SQLite file is deleted by an EXIT
# trap regardless of success or failure (Requirement 12.1).
#
# Usage:
#   scripts/ci/alembic_round_trip.sh [working_directory]
#
# When `working_directory` is omitted, the script defaults to
# `web/apps/admin-dashboard/backend` (the directory the design pins for
# alembic invocations). All `alembic` commands run from that directory.
#
# Exit codes:
#   0   All three alembic commands completed successfully.
#   non-zero   Propagates the exit code of the first failing alembic step.

set -euo pipefail
set -o pipefail

# --- Resolve working directory ------------------------------------------------

# Determine the repository root from this script's location so the default
# working directory resolves correctly regardless of where the script is
# invoked from.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"

default_workdir="${repo_root}/web/apps/admin-dashboard/backend"
workdir="${1:-${default_workdir}}"

if [[ ! -d "${workdir}" ]]; then
  printf 'alembic_round_trip: working directory not found: %s\n' "${workdir}" >&2
  exit 2
fi

# --- Compute ephemeral SQLite path and DATABASE_URL ---------------------------

tmp_root="${RUNNER_TEMP:-/tmp}"
mkdir -p -- "${tmp_root}"

db_path="${tmp_root}/alembic_check_$$_$(date +%s).db"

# Always use forward slashes in the SQLAlchemy URL even on platforms where the
# temp root contains backslashes; alembic/SQLAlchemy require POSIX paths in the
# URL form.
db_url_path="${db_path//\\//}"
DATABASE_URL="sqlite:///${db_url_path}"
export DATABASE_URL

# --- Cleanup trap -------------------------------------------------------------

# Save the script's exit status before cleanup and restore it after, so the
# trap never masks a non-zero exit code from any of the alembic commands.
final_status=0
cleanup() {
  local saved_status=$?
  if [[ "${final_status}" -eq 0 && "${saved_status}" -ne 0 ]]; then
    final_status="${saved_status}"
  fi
  # `rm -f` succeeds when the file is already gone; suppress its exit value
  # so a transient cleanup race never overrides the real script status.
  rm -f -- "${db_path}" 2>/dev/null || true
  exit "${final_status}"
}
trap cleanup EXIT

# --- Helper: run one alembic step with explicit $? handling -------------------

run_step() {
  local label="$1"
  shift

  printf '==> %s\n' "${label}"

  # Disable `set -e` for the single command so we can capture `$?` explicitly
  # (Requirements 12.2, 12.4 require explicit exit-code inspection rather than
  # relying solely on the shell's errexit behaviour).
  set +e
  ( cd -- "${workdir}" && timeout 300 "$@" )
  local rc=$?
  set -e

  if [[ "${rc}" -ne 0 ]]; then
    if [[ "${rc}" -eq 124 ]]; then
      printf 'alembic_round_trip: step "%s" exceeded 300s timeout (exit %d)\n' \
        "${label}" "${rc}" >&2
    else
      printf 'alembic_round_trip: step "%s" failed with exit code %d\n' \
        "${label}" "${rc}" >&2
    fi
    final_status="${rc}"
    exit "${rc}"
  fi
}

# --- Execute the three-step round trip ----------------------------------------

run_step 'alembic upgrade head (initial)' alembic upgrade head
run_step 'alembic downgrade base'         alembic downgrade base
run_step 'alembic upgrade head (replay)'  alembic upgrade head

printf 'alembic_round_trip: OK (upgrade head, downgrade base, upgrade head)\n'
final_status=0
exit 0
