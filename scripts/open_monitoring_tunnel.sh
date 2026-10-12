#!/usr/bin/env bash
set -euo pipefail

# Open the private Grafana and Uptime Kuma interfaces on this computer.
# Optionally pass a different SSH destination as the first argument.
ssh_target="${1:-ubuntu@rentalution}"

exec ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 3000:127.0.0.1:3000 \
  -L 3001:127.0.0.1:3001 \
  "$ssh_target"
