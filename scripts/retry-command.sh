#!/usr/bin/env bash

set -uo pipefail

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <command> [args...]" >&2
  exit 64
fi

attempts="${RETRY_ATTEMPTS:-5}"
retry_pattern="${RETRY_PATTERN:-Rate limit exceeded|Too Many Requests|timed out|ETIMEDOUT|ECONNRESET|Temporary failure|502 Bad Gateway|503 Service Unavailable|504 Gateway Timeout|Internal Server Error|Server Error|Unexpected HTTP response: 50[234]|The requested URL returned error: 50[234]|HTTP error 50[234]}"
skip_sleep="${RETRY_SKIP_SLEEP:-0}"

for attempt in $(seq 1 "$attempts"); do
  output=$("$@" 2>&1)
  status=$?

  if [ "$status" -eq 0 ]; then
    printf '%s\n' "$output"
    exit 0
  fi

  printf '%s\n' "$output"

  if ! printf '%s\n' "$output" | grep -Eqi "$retry_pattern"; then
    exit "$status"
  fi

  if [ "$attempt" -eq "$attempts" ]; then
    exit "$status"
  fi

  wait_seconds=$(printf '%s\n' "$output" | sed -n 's/.*retry in \([0-9][0-9]*\)s.*/\1/p' | tail -n 1)
  if [ -z "$wait_seconds" ]; then
    wait_seconds=$((attempt * 2))
  fi
  wait_seconds=$((wait_seconds + 1))

  echo "Retrying command in ${wait_seconds}s (attempt ${attempt}/${attempts})"
  if [ "$skip_sleep" != "1" ]; then
    sleep "$wait_seconds"
  fi
done
