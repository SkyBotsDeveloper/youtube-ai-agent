#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/restore_from_backup.sh <backup_path>" >&2
  exit 2
fi

cd "$(dirname "$0")/.."
python -m raatverse_agent db restore "$1" --confirm
