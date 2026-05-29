#!/usr/bin/env bash
# scripts/lib/compute_backoff.sh
#
# Sourceable helper that exposes ``compute_backoff_delay <count>`` so the
# host-side supervisor watchdog (``scripts/supervisor_watchdog.sh``) and its
# property-based test (``tests/scripts/test_watchdog_backoff.py``) can share a
# single, canonical implementation of the formula declared in design.md
# section C11 ("Restart-loop backoff") and Requirement 16.8:
#
#   delay(n) = 0                                                 if n < RESTART_THRESHOLD
#            = min(MAX_DELAY, BASE_DELAY * 2^(n - RESTART_THRESHOLD))  otherwise
#
# The function reads three configuration values with defaults that match
# R16.8 verbatim (5 restarts in a 60s window, 10s base, 120s cap):
#
#   RESTART_THRESHOLD  number of restart events that trigger backoff (default 5)
#   BASE_DELAY         initial backoff base in seconds                (default 10)
#   MAX_DELAY          cap on the backoff delay in seconds            (default 120)
#
# The ``: "${VAR:=default}"`` form preserves any value the caller has already
# set, so sourcing this file from another script is side-effect free apart
# from declaring the function and supplying defaults.
#
# This file is intentionally tiny and pure: no commands run when sourced, no
# external tools are invoked. That property is what makes it safe to source
# from a unit-test harness without dragging the watchdog's docker-events main
# loop along with it.

: "${RESTART_THRESHOLD:=5}"
: "${BASE_DELAY:=10}"
: "${MAX_DELAY:=120}"

compute_backoff_delay() {
  local count="$1"
  if [[ "$count" -lt "$RESTART_THRESHOLD" ]]; then
    printf '0\n'
    return 0
  fi

  local exponent=$((count - RESTART_THRESHOLD))
  # Cap the exponent to avoid integer overflow on very large counts; any
  # exponent >= 5 already exceeds MAX_DELAY (10 * 32 = 320 > 120), so the
  # ceiling clamp below absorbs the cap. We pick 30 because ``1 << 30`` is
  # safely within 32-bit signed arithmetic on every shell we target.
  if [[ "$exponent" -gt 30 ]]; then
    exponent=30
  fi

  local shift_value=$((1 << exponent))
  local delay=$((BASE_DELAY * shift_value))
  if [[ "$delay" -gt "$MAX_DELAY" ]]; then
    delay="$MAX_DELAY"
  fi
  printf '%s\n' "$delay"
}
