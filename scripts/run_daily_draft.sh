#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p outputs/logs
python -m raatverse_agent db init
python -m raatverse_agent workflow daily-draft --mock 2>&1 | tee -a outputs/logs/daily-draft.log
python -m raatverse_agent review queue 2>&1 | tee -a outputs/logs/review-queue.log
