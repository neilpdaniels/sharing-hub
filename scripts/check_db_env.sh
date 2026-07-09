#!/usr/bin/env sh
set -eu

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Env file not found: $ENV_FILE" >&2
    exit 1
fi

set +u
set -a
. "$ENV_FILE"
set +a
set -u

mask() {
    value="${1:-}"
    if [ -z "$value" ]; then
        printf '<missing>'
    else
        case "$value" in
            ??????*)
                printf '%s***' "$(printf '%s' "$value" | cut -c1-3)"
                ;;
            *)
                printf '***'
                ;;
        esac
    fi
}

echo "Loaded from: $ENV_FILE"
echo "POSTGRES_DB=$(mask "${POSTGRES_DB:-}")"
echo "POSTGRES_USER=$(mask "${POSTGRES_USER:-}")"
echo "POSTGRES_PASSWORD=$(mask "${POSTGRES_PASSWORD:-}")"
echo "POSTGRES_HOST=$(mask "${POSTGRES_HOST:-}")"
echo "POSTGRES_PORT=$(mask "${POSTGRES_PORT:-}")"
echo "DJANGO_SETTINGS_MODULE=$(mask "${DJANGO_SETTINGS_MODULE:-}")"
echo "DJANGO_ALLOWED_HOSTS=$(mask "${DJANGO_ALLOWED_HOSTS:-}")"
echo "DJANGO_CSRF_TRUSTED_ORIGINS=$(mask "${DJANGO_CSRF_TRUSTED_ORIGINS:-}")"

if [ "${CHECK_DB_CONNECTION:-0}" = "1" ]; then
    if command -v docker >/dev/null 2>&1; then
        echo "Testing DB connection via docker compose..."
        docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
            psql -U "${POSTGRES_USER:-rentalution}" -d "${POSTGRES_DB:-rentalution}" -c '\conninfo'
    else
        echo "docker not found; skipping DB connection test" >&2
    fi
fi
