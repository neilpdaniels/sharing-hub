#!/usr/bin/env sh
set -eu

worker_name="${1:-worker}@$(hostname)"

uv run celery -A rentalution inspect ping -d "$worker_name" --timeout=5 | grep -q pong
