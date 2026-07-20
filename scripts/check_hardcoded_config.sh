#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

status=0

for pattern in \
    GXnnXv3ggedOSG \
    0x4AAAAAADGXnnXv3ggedOSG \
    'swq!o4((s3(t15=f==-x%)aip!xlas0ob0zu@q0h0q*l6nr1l%' \
    'django-insecure-dp##n9ghn8^8%k+%86)x+ufg9!v%8ei2p!$5x9282p_e6=5n!h' \
    LqMIyzNTgEOnNrk_lBtVJA51693
do
    [ -n "$pattern" ] || continue
    matches="$(grep -RIn --include='*.py' --include='*.html' --include='*.yml' --include='*.yaml' --include='*.sh' --include='*.txt' --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude='check_hardcoded_config.sh' -- "$pattern" "$repo_root" || true)"
    if [ -n "$matches" ]; then
        printf '%s\n' "$matches" >&2
        printf 'Hardcoded config value found: %s\n' "$pattern" >&2
        status=1
    fi
done

exit "$status"
