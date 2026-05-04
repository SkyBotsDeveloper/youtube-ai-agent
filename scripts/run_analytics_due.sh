#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p outputs/logs
python -m raatverse_agent db init
python -m raatverse_agent workflow analytics-due --mock 2>&1 | tee -a outputs/logs/analytics-due.log
