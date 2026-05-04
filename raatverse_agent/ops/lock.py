from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from raatverse_agent.config import Settings


class WorkflowLockError(RuntimeError):
    pass


class WorkflowLock:
    def __init__(self, settings: Settings, name: str):
        self.settings = settings
        self.name = name
        self.path = Path(settings.workflow_log_dir) / "locks" / f"{name}.lock"
        self.acquired = False

    def __enter__(self) -> "WorkflowLock":
        if not self.settings.scheduler_lock_enabled:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clear_stale_lock_if_needed()
        payload = {
            "name": self.name,
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.path), flags)
        except FileExistsError as exc:
            raise WorkflowLockError(f"Workflow '{self.name}' is already locked: {self.path}") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.acquired and self.path.exists():
            self.path.unlink()
        self.acquired = False

    def _clear_stale_lock_if_needed(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            created_at = datetime.fromisoformat(str(payload.get("created_at")))
        except (json.JSONDecodeError, ValueError, TypeError):
            created_at = datetime.fromtimestamp(self.path.stat().st_mtime, tz=timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        stale_after = timedelta(minutes=self.settings.scheduler_lock_timeout_minutes)
        if datetime.now(timezone.utc) - created_at > stale_after:
            self.path.unlink()
