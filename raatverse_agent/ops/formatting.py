from __future__ import annotations

from raatverse_agent.ops.models import OpsStatus, ReviewQueue, WorkflowRun


def format_workflow_run(run: WorkflowRun) -> str:
    return (
        "RaatVerse workflow run\n"
        f"Run ID: {run.id}\n"
        f"Type: {run.workflow_type}\n"
        f"Status: {run.status}\n"
        f"Provider mode: {run.provider_mode}\n"
        f"Dry run: {run.dry_run}\n"
        f"Started: {run.started_at or 'None'}\n"
        f"Finished: {run.finished_at or 'None'}\n"
        f"Created script ID: {run.created_script_id or 'None'}\n"
        f"Created asset plan ID: {run.created_asset_plan_id or 'None'}\n"
        f"Created render ID: {run.created_render_id or 'None'}\n"
        f"Created upload ID: {run.created_upload_id or 'None'}\n"
        f"Summary: {run.summary}\n"
        f"Error: {run.error_message or 'None'}"
    )


def format_review_queue(queue: ReviewQueue) -> str:
    lines = [
        "RaatVerse review queue",
        f"Total pending: {queue.total_pending}",
        _section("Scripts pending review", queue.scripts_pending_review, "id", "title"),
        _section("Rejected scripts", queue.rejected_scripts, "id", "title"),
        _section("Approved scripts needing assets", queue.scripts_approved_needing_assets, "id", "title"),
        _section("Assets ready needing render", queue.assets_ready_needing_render, "id", "status"),
        _section("Renders ready needing upload prepare", queue.renders_ready_needing_upload_prepare, "id", "output_path"),
        _section("Uploads pending approval", queue.uploads_pending_approval, "id", "title"),
        _section("Uploads ready/private", queue.uploads_ready_private, "id", "status"),
        _section("Analytics due", queue.analytics_due, "youtube_upload_id", "due_windows"),
        _section("Failed workflows", queue.failed_workflows, "id", "workflow_type"),
    ]
    return "\n".join(lines)


def format_ops_status(status: OpsStatus) -> str:
    latest = (
        f"{status.latest_workflow_run.id} [{status.latest_workflow_run.status}] "
        f"{status.latest_workflow_run.workflow_type}"
        if status.latest_workflow_run
        else "None"
    )
    return (
        "RaatVerse operations status\n"
        f"Status: {status.status}\n"
        f"Automation mode: {status.automation_mode}\n"
        f"Daily stop after draft: {status.daily_stop_after_draft}\n"
        f"Auto upload enabled: {status.auto_upload}\n"
        f"Auto upload must be approved: {status.auto_upload_must_be_approved}\n"
        f"Scheduler lock enabled: {status.scheduler_lock_enabled}\n"
        f"Pending review count: {status.pending_review_count}\n"
        f"Latest workflow run: {latest}\n"
        f"Strategy: {status.strategy_summary or 'None'}"
    )


def format_ops_health(health: dict) -> str:
    warnings = health.get("warnings") or []
    warning_text = "\n".join(f"  - {warning}" for warning in warnings) if warnings else "  none"
    return (
        "RaatVerse operations health\n"
        f"Status: {health.get('status')}\n"
        f"Database ok: {health.get('db', {}).get('ok')}\n"
        f"Output writable: {health.get('storage', {}).get('output_writable')}\n"
        f"Backup writable: {health.get('storage', {}).get('backup_writable')}\n"
        f"FFmpeg available: {health.get('ffmpeg', {}).get('available')}\n"
        f"Dashboard token required: {health.get('dashboard', {}).get('require_token')}\n"
        f"Pending review count: {health.get('pending_review_count')}\n"
        "Warnings:\n"
        f"{warning_text}"
    )


def format_ops_doctor(health: dict) -> str:
    warnings = health.get("warnings") or []
    if not warnings:
        return "RaatVerse ops doctor\nNo warnings found."
    return "RaatVerse ops doctor\nWarnings:\n" + "\n".join(f"  - {warning}" for warning in warnings)


def format_e2e_check(result: dict) -> str:
    run = result.get("full_mock_run", {})
    health = result.get("ops_health", {})
    return (
        "RaatVerse E2E mock check\n"
        f"Status: {result.get('status')}\n"
        f"Database ok: {health.get('db', {}).get('ok')}\n"
        f"Backup: {result.get('backup_path') or result.get('backup_error') or 'None'}\n"
        f"Full mock run: {run.get('id')} [{run.get('status')}]\n"
        f"Pending review count: {health.get('pending_review_count')}\n"
        f"Warnings: {len(health.get('warnings') or [])}"
    )


def _section(title: str, items: list[dict], id_key: str, label_key: str) -> str:
    if not items:
        return f"{title}: none"
    lines = [f"{title}:"]
    for item in items[:20]:
        lines.append(f"  - {item.get(id_key)}: {item.get(label_key)}")
    if len(items) > 20:
        lines.append(f"  ... and {len(items) - 20} more")
    return "\n".join(lines)
