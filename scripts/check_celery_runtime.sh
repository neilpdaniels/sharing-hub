#!/usr/bin/env sh
set -eu

worker_name="${1:-worker}@$(hostname)"

response="$(uv run celery -A rentalution inspect ping --destination="$worker_name" --timeout=10 2>&1)" || {
    printf '%s\n' "$response" >&2
    exit 1
}

printf '%s\n' "$response"
printf '%s\n' "$response" | grep -F -q -- "${worker_name}: OK"
