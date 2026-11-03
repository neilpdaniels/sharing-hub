#!/bin/sh
# The service has Docker socket access solely to read the named application's
# logs. Docker's socket is privileged, so do not add this mount to web/worker.
set -eu

review_hours="${LOG_REVIEW_HOURS:-6}"
sleep_seconds="$((review_hours * 60 * 60))"
email_args="--email"
if [ "${LOG_REVIEW_EMAIL_OK_SUMMARIES:-0}" != "1" ]; then
    email_args="$email_args --email-on-problems-only"
fi

while :; do
    if [ "${LOG_REVIEW_SCHEDULED_ENABLED:-0}" = "1" ]; then
        # shellcheck disable=SC2086 # Intentional split of the two fixed flags.
        python manage.py review_production_logs --source docker --hours "$review_hours" $email_args \
            || echo "LOG_REVIEW_FAILED at $(date -u +%FT%TZ)" >&2
    else
        echo "LOG_REVIEW_DISABLED" >&2
    fi
    sleep "$sleep_seconds"
done
