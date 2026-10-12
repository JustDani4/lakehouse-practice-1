#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Restore the already populated local stack without rerunning the experiment.
colima start lakehouse --cpu 3 --memory 4 --disk 12 --root-disk 10 --vm-type vz --activate=false
mkdir -p .docker-client
printf '%s\n' '{}' > .docker-client/config.json
export DOCKER_CONFIG="$PWD/.docker-client"
export DOCKER_HOST="unix://$HOME/.colima/lakehouse/docker.sock"
if docker compose version >/dev/null 2>&1; then
  docker compose up -d
  docker compose ps
else
  docker-compose up -d
  docker-compose ps
fi
