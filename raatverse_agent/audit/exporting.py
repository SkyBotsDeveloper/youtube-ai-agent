from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from raatverse_agent.audit.models import AuditLog
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository


def parse_datetime_filter(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def filtered_audit_logs(
    repository: RaatVerseRepository,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 500,
) -> list[AuditLog]:
    return repository.list_audit_logs(
        action=action,
        entity_type=entity_type,
        since=parse_datetime_filter(since),
        until=parse_datetime_filter(until),
        limit=limit,
    )


def audit_logs_payload(logs: list[AuditLog]) -> dict:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "schema": "raatverse-audit-export-v1",
        "count": len(logs),
        "audit_logs": [log.model_dump(mode="json") for log in logs],
    }


def export_audit_json(settings: Settings, logs: list[AuditLog]) -> Path:
    export_dir = Path(settings.audit_export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = export_dir / f"raatverse-audit-{timestamp}.json"
    path.write_text(json.dumps(audit_logs_payload(logs), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_audit_csv(settings: Settings, logs: list[AuditLog]) -> Path:
    export_dir = Path(settings.audit_export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = export_dir / f"raatverse-audit-{timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "created_at",
                "actor",
                "action",
                "entity_type",
                "entity_id",
                "before_status",
                "after_status",
                "reason",
                "ip_address",
                "user_agent",
                "metadata",
            ],
        )
        writer.writeheader()
        for log in logs:
            writer.writerow(
                {
                    "id": log.id,
                    "created_at": log.created_at.isoformat(),
                    "actor": log.actor,
                    "action": log.action,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                    "before_status": log.before_status,
                    "after_status": log.after_status,
                    "reason": log.reason,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "metadata": json.dumps(log.metadata, ensure_ascii=False),
                }
            )
    return path
