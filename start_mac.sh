#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# A separate profile; does not change the active Docker Desktop context.
colima start lakehouse --cpu 3 --memory 4 --disk 12 --root-disk 10 --vm-type vz --activate=false
mkdir -p .docker-client
printf '%s\n' '{}' > .docker-client/config.json
export DOCKER_CONFIG="$PWD/.docker-client"
export DOCKER_HOST="unix://$HOME/.colima/lakehouse/docker.sock"
exec bash run_all.sh
