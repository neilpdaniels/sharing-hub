#!/usr/bin/env sh
set -eu

worker_name="${1:-worker}@$(hostname)"

uv run celery -A rentalution inspect ping --timeout=5 | grep -F -q -- "${worker_name}: OK"
