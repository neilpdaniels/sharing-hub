#!/bin/sh
# The service queries Loki, so it needs neither Docker's socket nor host log files.
set -eu

review_hours="${LOG_REVIEW_HOURS:-6}"
review_minutes="${LOG_REVIEW_LOOKBACK_MINUTES:-$((review_hours * 60))}"
sleep_seconds="$((review_hours * 60 * 60))"
email_args="--email"
if [ "${LOG_REVIEW_EMAIL_OK_SUMMARIES:-0}" != "1" ]; then
    email_args="$email_args --email-on-problems-only"
fi

while :; do
    if [ "${LOG_REVIEW_SCHEDULED_ENABLED:-0}" = "1" ]; then
        # shellcheck disable=SC2086 # Intentional split of the two fixed flags.
        python manage.py review_production_logs --source loki --minutes "$review_minutes" $email_args \
            || echo "LOG_REVIEW_FAILED at $(date -u +%FT%TZ)" >&2
    else
        echo "LOG_REVIEW_DISABLED" >&2
    fi
    sleep "$sleep_seconds"
done
