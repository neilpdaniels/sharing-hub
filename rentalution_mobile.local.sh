#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-dev}"
shift || true

ENV_FILE="${ROOT_DIR}/.rentalution_mobile.${mode}.env"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

case "$mode" in
  dev)
    exec "${ROOT_DIR}/run_rentalution_mobile_dev" "$@"
    ;;
  prod)
    exec "${ROOT_DIR}/run_rentalution_mobile_prod" "$@"
    ;;
  *)
    echo "Usage: $0 [dev|prod]"
    exit 1
    ;;
esac
