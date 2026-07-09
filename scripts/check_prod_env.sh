#!/usr/bin/env sh
set -eu

missing=""

check_var() {
    name="$1"
    value="$(printenv "$name" 2>/dev/null || true)"
    if [ -z "$value" ]; then
        missing="${missing}${name}\n"
    fi
}

check_alt_var() {
    name1="$1"
    name2="$2"
    value1="$(printenv "$name1" 2>/dev/null || true)"
    value2="$(printenv "$name2" 2>/dev/null || true)"
    if [ -z "$value1" ] && [ -z "$value2" ]; then
        missing="${missing}${name1} or ${name2}\n"
    fi
}

check_var DJANGO_ALLOWED_HOSTS
check_var DJANGO_CSRF_TRUSTED_ORIGINS
check_alt_var DJANGO_SECRET_KEY RENTALUTION_SECRET_KEY
check_var POSTGRES_DB
check_var POSTGRES_USER
check_var POSTGRES_PASSWORD
check_var POSTGRES_HOST
check_var POSTGRES_PORT
check_var CELERY_BROKER_URL
check_var CELERY_RESULT_BACKEND
check_var STRIPE_CONNECT_PUBLIC_KEY
check_var STRIPE_CONNECT_SECRET_KEY
check_var STRIPE_CONNECT_WEBHOOK_SECRET
check_var TWILIO_ACCOUNT_SID
check_var TWILIO_AUTH_TOKEN
check_var TWILIO_VERIFY_SERVICE_SID
check_var TURNSTILE_SITE_KEY
check_var TURNSTILE_SECRET_KEY
check_var FCM_PROJECT_ID
check_var FCM_SENDER_ID
check_var FCM_SERVICE_ACCOUNT_FILE
check_var DEFAULT_FROM_EMAIL
check_var SITE_URL
check_var ENVIRONMENT_NAME
check_var ENVIRONMENT_COLOR

if [ -n "$missing" ]; then
    printf 'Missing or blank environment variables:\n'
    printf '%b' "$missing"
    exit 1
fi

printf 'All requested environment variables are set.\n'
