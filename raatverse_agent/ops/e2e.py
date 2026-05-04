from __future__ import annotations

from raatverse_agent.db.persistence import PersistenceError, backup_database, database_status
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.ops.health import ops_health_payload
from raatverse_agent.ops.workflow import WorkflowOrchestrationService
from raatverse_agent.config import Settings


def run_e2e_check(
    *,
    settings: Settings,
    repository: RaatVerseRepository,
    mock: bool = True,
) -> dict:
    if not mock:
        raise ValueError("E2E check is mock-only in Phase 10 and must not call real external APIs.")

    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    db = database_status(settings)
    backup_path = None
    backup_error = None
    try:
        backup_path = str(backup_database(settings))
    except PersistenceError as exc:
        backup_error = str(exc)

    full_mock = service.run_full_mock()
    queue = service.review_queue()
    latest_runs = repository.list_workflow_runs(limit=1)
    health = ops_health_payload(
        settings=settings,
        queue=queue,
        latest_workflow_run=latest_runs[0] if latest_runs else None,
    )
    return {
        "status": "ok" if full_mock.status == "success" and health["db"]["ok"] else "warning",
        "db_status": db,
        "backup_path": backup_path,
        "backup_error": backup_error,
        "full_mock_run": full_mock.model_dump(mode="json"),
        "review_queue": queue.model_dump(mode="json"),
        "ops_health": health,
    }
