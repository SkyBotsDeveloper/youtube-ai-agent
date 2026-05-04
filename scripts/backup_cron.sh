#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python -m raatverse_agent db backup
python -m raatverse_agent db export-json
