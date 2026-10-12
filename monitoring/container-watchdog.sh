#!/bin/sh
# Detect stopped and repeatedly restarted production containers. Docker's Unix
# socket is required solely to inspect the local Compose services.
set -eu

project="${COMPOSE_PROJECT_NAME:-rentalution}"
services="web worker video-worker catalog-ai-worker beat db redis"
state_dir="/var/lib/container-watchdog"
mkdir -p "$state_dir"

while :; do
    for service in $services; do
        container_id="$(docker ps -aq \
            --filter "label=com.docker.compose.project=$project" \
            --filter "label=com.docker.compose.service=$service" | head -n 1)"

        if [ -z "$container_id" ]; then
            echo "CONTAINER_WATCHDOG_NOT_RUNNING service=$service reason=container_missing"
            continue
        fi

        status="$(docker inspect --format '{{.State.Status}}' "$container_id")"
        if [ "$status" != "running" ]; then
            echo "CONTAINER_WATCHDOG_NOT_RUNNING service=$service status=$status"
            continue
        fi

        restart_count="$(docker inspect --format '{{.RestartCount}}' "$container_id")"
        state_file="$state_dir/$service.restart-count"
        previous_count=0
        if [ -f "$state_file" ]; then
            previous_count="$(cat "$state_file")"
        fi

        if [ "$restart_count" -gt "$previous_count" ]; then
            echo "CONTAINER_WATCHDOG_RESTARTED service=$service count=$restart_count"
        fi
        printf '%s\n' "$restart_count" > "$state_file"
    done

    sleep 60
done
