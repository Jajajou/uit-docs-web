#!/usr/bin/env bash
#
# idempotency_diff.sh
#
# Compares two replay summaries produced by `.github/workflows/ci-idempotency.yml`
# for a single (workflow, commit) pair. Each replay directory MUST contain:
#   conclusion.txt       single token: "success" or "failure"
#   artifacts.txt        sorted list of artifact filenames (one per line)
#   <pytest|vitest>.junit.xml   JUnit XML report (optional; absent => empty test set)
#
# Exits 0 when the two passes agree on conclusion, test name set, and
# artifact filename set. Exits 1 with a structured-error JSON line on
# stdout otherwise.
#
# Required env vars:
#   A_DIR                directory of pass A
#   B_DIR                directory of pass B
#   REPLAYED_WORKFLOW    one of {frontend-ci, backend-ci, langgraph-ci}
#   REPLAYED_COMMIT      commit SHA being replayed
#
# Validates Property 8 / CP-1 (Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3,
# 4.1, 4.2, 4.3) at runtime by failing the workflow on any mismatch.

set -euo pipefail

: "${A_DIR:?A_DIR is required}"
: "${B_DIR:?B_DIR is required}"
: "${REPLAYED_WORKFLOW:?REPLAYED_WORKFLOW is required}"
: "${REPLAYED_COMMIT:?REPLAYED_COMMIT is required}"

emit_error() {
  local kind="$1"
  local detail="$2"
  printf '{"code":"CI_IDEMPOTENCY_MISMATCH","kind":"%s","workflow":"%s","commit":"%s","detail":%s}\n' \
    "$kind" "$REPLAYED_WORKFLOW" "$REPLAYED_COMMIT" "$detail"
}

# JSON-escape a string for embedding via printf %s.
json_escape() {
  python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read()))'
}

# Extract the sorted set of fully-qualified test names from a JUnit XML
# file. Empty file or missing file => empty set. We use python rather
# than xmllint to avoid an apt dependency on the runner.
extract_tests() {
  local junit_path="$1"
  if [[ ! -s "$junit_path" ]]; then
    return 0
  fi
  python3 - "$junit_path" <<'PY'
import sys
import xml.etree.ElementTree as ET

path = sys.argv[1]
try:
    tree = ET.parse(path)
except ET.ParseError:
    sys.exit(0)

names = set()
for case in tree.iter('testcase'):
    classname = case.get('classname', '') or ''
    name = case.get('name', '') or ''
    if classname:
        names.add(f"{classname}::{name}")
    else:
        names.add(name)

for n in sorted(names):
    print(n)
PY
}

junit_a=""
junit_b=""
for candidate in pytest.junit.xml vitest.junit.xml; do
  [[ -f "$A_DIR/$candidate" ]] && junit_a="$A_DIR/$candidate"
  [[ -f "$B_DIR/$candidate" ]] && junit_b="$B_DIR/$candidate"
done

conc_a="$(cat "$A_DIR/conclusion.txt" 2>/dev/null || echo missing)"
conc_b="$(cat "$B_DIR/conclusion.txt" 2>/dev/null || echo missing)"

if [[ "$conc_a" != "$conc_b" ]]; then
  detail=$(printf '{"pass_a":"%s","pass_b":"%s"}' "$conc_a" "$conc_b")
  emit_error "conclusion" "$detail"
  exit 1
fi

tests_a="$(extract_tests "${junit_a:-/dev/null}" || true)"
tests_b="$(extract_tests "${junit_b:-/dev/null}" || true)"

if [[ "$tests_a" != "$tests_b" ]]; then
  diff_payload="$(diff <(printf '%s\n' "$tests_a") <(printf '%s\n' "$tests_b") || true)"
  detail="$(printf '%s' "$diff_payload" | json_escape)"
  emit_error "test_names" "$detail"
  exit 1
fi

artifacts_a="$(cat "$A_DIR/artifacts.txt" 2>/dev/null || true)"
artifacts_b="$(cat "$B_DIR/artifacts.txt" 2>/dev/null || true)"

if [[ "$artifacts_a" != "$artifacts_b" ]]; then
  diff_payload="$(diff <(printf '%s\n' "$artifacts_a") <(printf '%s\n' "$artifacts_b") || true)"
  detail="$(printf '%s' "$diff_payload" | json_escape)"
  emit_error "artifacts" "$detail"
  exit 1
fi

printf 'CI idempotency replay matched: workflow=%s commit=%s conclusion=%s\n' \
  "$REPLAYED_WORKFLOW" "$REPLAYED_COMMIT" "$conc_a"
