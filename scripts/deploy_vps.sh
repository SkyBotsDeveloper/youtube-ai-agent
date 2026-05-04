#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m raatverse_agent db backup || true
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs --tail=80 raatverse-agent
