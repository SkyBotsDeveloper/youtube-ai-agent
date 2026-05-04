from __future__ import annotations

from raatverse_agent.audit.models import ApprovalEvent, AuditLog


def format_audit_log(log: AuditLog) -> str:
    return (
        "RaatVerse audit log\n"
        f"ID: {log.id}\n"
        f"Actor: {log.actor}\n"
        f"Action: {log.action}\n"
        f"Entity: {log.entity_type}#{log.entity_id or 'None'}\n"
        f"Status: {log.before_status or 'None'} -> {log.after_status or 'None'}\n"
        f"Reason: {log.reason or 'None'}\n"
        f"Created: {log.created_at}\n"
        f"Metadata: {log.metadata or {}}"
    )


def format_audit_log_line(log: AuditLog) -> str:
    return (
        f"{log.id}: {log.created_at.isoformat()} {log.actor} {log.action} "
        f"{log.entity_type}#{log.entity_id or 'None'} "
        f"{log.before_status or '-'}->{log.after_status or '-'}"
    )


def format_approval_event_line(event: ApprovalEvent) -> str:
    return (
        f"{event.id}: {event.created_at.isoformat()} {event.actor} {event.action} "
        f"{event.entity_type}#{event.entity_id} comment={event.comment or 'None'}"
    )
