#!/usr/bin/env bash
# scripts/ci/check_requirements_pinned.sh
#
# Lockfile-pin guard for the admin-dashboard backend CI (Requirements 19.3, 19.5).
#
# Reads a pip requirements file and exits non-zero if any non-comment,
# non-empty entry lacks the literal `==` exact-version pin operator. Each
# offending line is printed on stdout, one per line, before the script exits.
#
# Usage:
#   scripts/ci/check_requirements_pinned.sh [requirements_file]
#
# Defaults to `requirements.txt` in the current working directory when no
# argument is supplied. Designed to be invoked from `backend-ci.yml` before
# `pip install` runs, so an unpinned dependency fails the workflow before any
# resolution drift can occur.
#
# Behaviour:
#   * Blank lines and lines whose first non-whitespace character is `#` are
#     skipped.
#   * Trailing inline comments (everything from the first `#` to end-of-line)
#     are stripped before the pin check.
#   * Backslash line-continuations (`\` at EOL) are joined with the next
#     physical line, mirroring pip's own parsing.
#   * Recursive include directives (`-r other.txt`, `--requirement other.txt`,
#     `-c other.txt`, `--constraint other.txt`) are treated as comments and
#     skipped without recursion (the referenced file must be checked
#     separately if needed).
#   * Any remaining entry that does not contain `==` is reported as unpinned.
#
# Exit codes:
#   0   All entries pinned with `==`.
#   1   One or more entries lack `==` (each is printed on stdout).
#   2   Requirements file does not exist or is unreadable.

set -euo pipefail

req_file="${1:-requirements.txt}"

if [[ ! -f "$req_file" ]]; then
  printf 'check_requirements_pinned: file not found: %s\n' "$req_file" >&2
  exit 2
fi
if [[ ! -r "$req_file" ]]; then
  printf 'check_requirements_pinned: file not readable: %s\n' "$req_file" >&2
  exit 2
fi

# trim leading and trailing ASCII whitespace from $1, echo result.
trim() {
  local s="$1"
  # strip leading whitespace
  s="${s#"${s%%[![:space:]]*}"}"
  # strip trailing whitespace
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

is_reference_directive() {
  # Match `-r FILE`, `--requirement FILE`, `--requirement=FILE`,
  # `-c FILE`, `--constraint FILE`, `--constraint=FILE`.
  local s="$1"
  [[ "$s" =~ ^(-r|--requirement|-c|--constraint)([[:space:]]|=|$) ]]
}

bad=0
buffer=""

# Read every physical line including the final one even if it lacks a newline.
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  # Strip a single trailing CR so files with CRLF endings parse correctly.
  raw_line="${raw_line%$'\r'}"

  # Line-continuation: if the physical line ends with a single backslash,
  # accumulate it (without the backslash) and read the next physical line.
  if [[ "$raw_line" == *\\ ]]; then
    buffer+="${raw_line%\\} "
    continue
  fi

  # Combine any pending continuation buffer with the current line.
  line="${buffer}${raw_line}"
  buffer=""

  # Strip trailing inline comment (everything from the first `#` onward).
  line="${line%%#*}"

  trimmed="$(trim "$line")"

  # Skip blank lines (this also covers lines that were entirely a comment).
  [[ -z "$trimmed" ]] && continue

  # Skip recursive `-r`/`-c` includes; per spec we do not recurse here.
  if is_reference_directive "$trimmed"; then
    continue
  fi

  # Pin check: the literal `==` must appear somewhere in the entry.
  if [[ "$trimmed" != *"=="* ]]; then
    printf 'Unpinned: %s\n' "$trimmed"
    bad=1
  fi
done < "$req_file"

# Handle a dangling continuation buffer (file ended on a `\` continuation).
if [[ -n "$buffer" ]]; then
  line="${buffer%%#*}"
  trimmed="$(trim "$line")"
  if [[ -n "$trimmed" ]] && ! is_reference_directive "$trimmed"; then
    if [[ "$trimmed" != *"=="* ]]; then
      printf 'Unpinned: %s\n' "$trimmed"
      bad=1
    fi
  fi
fi

exit "$bad"
