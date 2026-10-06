#!/usr/bin/env sh
set -eu

if [ "$#" -eq 0 ]; then
    set -- "worker@$(hostname)"
fi

# A Redis/Celery 5.6 control client can receive a broadcast reply while a
# destination-filtered request to the same node gets no reply.  Verify the
# named worker from the complete control response instead.
response="$(uv run celery -A rentalution inspect ping --timeout=10 2>&1)" || {
    printf '%s\n' "$response" >&2
    exit 1
}

printf '%s\n' "$response"
for worker_name in "$@"; do
    printf '%s\n' "$response" | grep -F -q -- "${worker_name}: OK" || {
        printf 'Expected worker did not reply: %s\n' "$worker_name" >&2
        exit 1
    }
done
