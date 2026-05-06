from __future__ import annotations

import argparse
import json
import sys

from raatverse_agent.audit.exporting import export_audit_csv, export_audit_json, filtered_audit_logs
from raatverse_agent.audit.formatting import (
    format_approval_event_line,
    format_audit_log,
    format_audit_log_line,
)
from raatverse_agent.analytics.formatting import (
    format_analytics_snapshot,
    format_category_score,
    format_due_snapshots,
    format_strategy_recommendation,
)
from raatverse_agent.analytics.models import AnalyticsFetchAllRequest, AnalyticsFetchRequest
from raatverse_agent.analytics.service import AnalyticsWorkflowError, create_analytics_workflow_service
from raatverse_agent.analytics.strategy import StrategyLearningService
from raatverse_agent.assets.errors import AssetWorkflowError
from raatverse_agent.assets.formatting import (
    format_asset_plan,
    format_asset_quality_report,
    format_audio_asset,
)
from raatverse_agent.assets.models import AssetPreparationRequest, TTSGenerationRequest
from raatverse_agent.assets.quality import analyze_asset_plan
from raatverse_agent.assets.service import (
    create_asset_preparation_service,
    create_tts_asset_service,
)
from raatverse_agent.config import get_settings
from raatverse_agent.db.persistence import (
    PersistenceError,
    backup_database,
    database_status,
    export_database_json,
    import_database_json,
    list_backups,
    restore_database,
)
from raatverse_agent.db.migrations import (
    MigrationError,
    check_migrations,
    create_migration,
    current_revision,
    migration_history,
    safe_upgrade_database,
    upgrade_database,
)
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.notifications.formatting import format_notification_result
from raatverse_agent.notifications.providers import NotificationError
from raatverse_agent.notifications.service import NotificationService
from raatverse_agent.ops.formatting import (
    format_e2e_check,
    format_ops_doctor,
    format_ops_health,
    format_ops_status,
    format_review_queue,
    format_workflow_run,
)
from raatverse_agent.ops.e2e import run_e2e_check
from raatverse_agent.ops.health import ops_health_payload
from raatverse_agent.ops.models import WorkflowRequest
from raatverse_agent.ops.workflow import WorkflowOrchestrationService
from raatverse_agent.pipeline.formatting import format_pipeline_summary
from raatverse_agent.pipeline.runner import PipelineRunner
from raatverse_agent.rendering.errors import RenderWorkflowError
from raatverse_agent.rendering.formatting import format_render_validation, format_video_render
from raatverse_agent.rendering.models import RenderRequest
from raatverse_agent.rendering.service import create_render_workflow_service
from raatverse_agent.release.formatting import (
    format_release_checklist,
    format_release_prepare,
    format_release_status,
)
from raatverse_agent.release.service import (
    prepare_release,
    release_checklist,
    release_notes,
    release_status,
)
from raatverse_agent.script_generation.formatting import (
    format_script_draft,
    format_script_generation_response,
)
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService, create_script_draft_generator
from raatverse_agent.services.gemini import LLMConfigurationError, LLMProviderError
from raatverse_agent.youtube.formatting import (
    format_metadata_preview,
    format_token_status,
    format_youtube_upload,
)
from raatverse_agent.youtube.models import YouTubeScheduleRequest, YouTubeUploadRequest
from raatverse_agent.youtube.oauth import (
    YouTubeOAuthError,
    build_oauth_url,
    exchange_code_for_token,
    revoke_local_token,
    token_status,
)
from raatverse_agent.youtube.service import YouTubeWorkflowError, create_youtube_upload_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m raatverse_agent",
        description="RaatVerse AI YouTube Shorts Agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    db_parser = subparsers.add_parser("db", help="Database commands")
    db_subparsers = db_parser.add_subparsers(dest="db_command", required=True)
    db_subparsers.add_parser("init", help="Initialize database tables")
    db_subparsers.add_parser("backup", help="Create a timestamped SQLite backup")
    db_subparsers.add_parser("backups", help="List SQLite backups")
    db_subparsers.add_parser("export-json", help="Export database tables to JSON")
    import_json = db_subparsers.add_parser("import-json", help="Import JSON into an empty database")
    import_json.add_argument("path", help="JSON export path")
    import_json.add_argument("--confirm", action="store_true", help="Confirm import into current database")
    restore = db_subparsers.add_parser("restore", help="Restore a SQLite backup")
    restore.add_argument("backup_path", help="SQLite backup path")
    restore.add_argument("--confirm", action="store_true", help="Confirm overwrite of current SQLite database")
    db_subparsers.add_parser("status", help="Show database status")
    migrate = db_subparsers.add_parser("migrate", help="Create a new Alembic migration revision")
    migrate.add_argument("--message", default="schema update", help="Migration message")
    upgrade = db_subparsers.add_parser("upgrade", help="Run Alembic migrations")
    upgrade.add_argument("--revision", default="head", help="Target revision")
    db_subparsers.add_parser("current", help="Show current Alembic revision")
    db_subparsers.add_parser("history", help="Show Alembic migration history")
    safe_upgrade = db_subparsers.add_parser("safe-upgrade", help="Backup SQLite then run Alembic upgrade")
    safe_upgrade.add_argument("--revision", default="head", help="Target revision")
    db_subparsers.add_parser("check-migrations", help="Check current and pending Alembic migrations")

    pipeline_parser = subparsers.add_parser("pipeline", help="Pipeline commands")
    pipeline_subparsers = pipeline_parser.add_subparsers(dest="pipeline_command", required=True)
    run_parser = pipeline_subparsers.add_parser("run", help="Run a pipeline")
    run_parser.add_argument(
        "--mock",
        action="store_true",
        help="Run the Phase 1 mock pipeline. Required until real providers are implemented.",
    )

    script_parser = subparsers.add_parser("script", help="Script draft commands")
    script_subparsers = script_parser.add_subparsers(dest="script_command", required=True)

    script_generate = script_subparsers.add_parser("generate", help="Generate a script draft")
    script_generate.add_argument("--category", required=False, help="Script category, e.g. horror")
    script_generate.add_argument(
        "--auto-category",
        action="store_true",
        help="Select the category from learned category scores.",
    )
    script_generate.add_argument("--story-type", required=False, help="Optional story type override")
    script_generate.add_argument("--seed", required=False, help="Optional premise seed")
    script_generate.add_argument(
        "--mock",
        action="store_true",
        help="Use the local mock script generator instead of a real LLM provider.",
    )

    script_list = script_subparsers.add_parser("list", help="List script drafts")
    script_list.add_argument("--status", required=False, help="Filter by draft status")
    script_list.add_argument("--limit", type=int, default=20, help="Maximum drafts to list")

    script_show = script_subparsers.add_parser("show", help="Show a script draft")
    script_show.add_argument("id", type=int, help="Draft database ID")

    script_approve = script_subparsers.add_parser("approve", help="Approve a script draft")
    script_approve.add_argument("id", type=int, help="Draft database ID")
    script_approve.add_argument("--comment", required=False, help="Optional approval comment")

    script_reject = script_subparsers.add_parser("reject", help="Reject a script draft")
    script_reject.add_argument("id", type=int, help="Draft database ID")
    script_reject.add_argument("--reason", required=True, help="Reason for rejection")
    script_reject.add_argument("--comment", required=False, help="Optional extra review comment")

    script_regenerate = script_subparsers.add_parser(
        "regenerate",
        help="Regenerate a rejected script draft into a new draft",
    )
    script_regenerate.add_argument("id", type=int, help="Rejected draft database ID")
    script_regenerate.add_argument(
        "--mock",
        action="store_true",
        help="Use the local mock script generator instead of a real LLM provider.",
    )

    tts_parser = subparsers.add_parser("tts", help="Narration audio commands")
    tts_subparsers = tts_parser.add_subparsers(dest="tts_command", required=True)
    tts_generate = tts_subparsers.add_parser("generate", help="Generate narration audio")
    tts_generate.add_argument("script_id", type=int, help="Approved script draft ID")
    tts_generate.add_argument("--mock", action="store_true", help="Use mock TTS")
    tts_generate.add_argument(
        "--force",
        action="store_true",
        help="Allow generation for a script that is not approved",
    )

    assets_parser = subparsers.add_parser("assets", help="Asset preparation commands")
    assets_subparsers = assets_parser.add_subparsers(dest="assets_command", required=True)
    assets_prepare = assets_subparsers.add_parser("prepare", help="Prepare audio and media assets")
    assets_prepare.add_argument("script_id", type=int, help="Approved script draft ID")
    assets_prepare.add_argument("--mock", action="store_true", help="Use mock TTS and media")
    assets_prepare.add_argument(
        "--force",
        action="store_true",
        help="Allow preparation for a script that is not approved",
    )
    assets_prepare.add_argument(
        "--download",
        action="store_true",
        help="Download selected stock media to the local cache when using real providers.",
    )
    assets_prepare.add_argument("--note", required=False, help="Optional operator note")

    assets_list = assets_subparsers.add_parser("list", help="List asset plans")
    assets_list.add_argument("--status", required=False, help="Filter by asset status")
    assets_list.add_argument("--limit", type=int, default=20, help="Maximum plans to list")

    assets_show = assets_subparsers.add_parser("show", help="Show an asset plan")
    assets_show.add_argument("id", type=int, help="Asset plan database ID")
    assets_quality = assets_subparsers.add_parser("quality", help="Show asset media quality report")
    assets_quality.add_argument("id", type=int, help="Asset plan database ID")

    render_parser = subparsers.add_parser("render", help="Video render commands")
    render_subparsers = render_parser.add_subparsers(dest="render_command", required=True)

    render_create = render_subparsers.add_parser("create", help="Create a local video render")
    render_create.add_argument("asset_plan_id", type=int, help="Asset plan database ID")
    render_create.add_argument("--mock", action="store_true", help="Use mock renderer")
    render_create.add_argument(
        "--force",
        action="store_true",
        help="Allow rendering when validation has blocking issues",
    )
    render_create.add_argument("--note", required=False, help="Optional operator note")
    render_create.add_argument(
        "--strict-quality",
        action="store_true",
        help="Block rendering when media/audio quality preflight warnings are present",
    )

    render_list = render_subparsers.add_parser("list", help="List video renders")
    render_list.add_argument("--status", required=False, help="Filter by render status")
    render_list.add_argument("--limit", type=int, default=20, help="Maximum renders to list")

    render_show = render_subparsers.add_parser("show", help="Show a video render")
    render_show.add_argument("id", type=int, help="Render database ID")

    render_validate = render_subparsers.add_parser("validate", help="Validate an asset plan for rendering")
    render_validate.add_argument("asset_plan_id", type=int, help="Asset plan database ID")
    render_validate.add_argument("--force", action="store_true", help="Show forced validation result")
    render_validate.add_argument(
        "--strict-quality",
        action="store_true",
        help="Treat media/audio quality warnings as validation issues",
    )

    youtube_parser = subparsers.add_parser("youtube", help="YouTube OAuth and upload commands")
    youtube_subparsers = youtube_parser.add_subparsers(dest="youtube_command", required=True)

    youtube_subparsers.add_parser("oauth-url", help="Print Google OAuth authorization URL")
    exchange = youtube_subparsers.add_parser("exchange-code", help="Exchange OAuth code for local token file")
    exchange.add_argument("code", help="Authorization code from Google OAuth redirect")
    youtube_subparsers.add_parser("token-status", help="Show local/env YouTube token status")
    youtube_subparsers.add_parser("revoke-local-token", help="Delete local YouTube token file")

    preview = youtube_subparsers.add_parser("metadata-preview", help="Preview YouTube metadata")
    preview.add_argument("render_id", type=int, help="Video render ID")

    prepare = youtube_subparsers.add_parser("prepare-upload", help="Create pending upload metadata")
    prepare.add_argument("render_id", type=int, help="Video render ID")
    prepare.add_argument("--note", required=False, help="Optional operator note")

    approve = youtube_subparsers.add_parser("approve-upload", help="Approve an upload record")
    approve.add_argument("upload_id", type=int, help="YouTube upload ID")
    approve.add_argument("--comment", required=False, help="Optional upload approval comment")

    upload_cmd = youtube_subparsers.add_parser("upload", help="Upload an approved render")
    upload_cmd.add_argument("upload_id", type=int, help="YouTube upload ID")
    upload_cmd.add_argument("--mock", action="store_true", help="Use mock uploader")
    upload_cmd.add_argument(
        "--approve-now",
        action="store_true",
        help="Approve immediately for mock/dev dry runs",
    )

    schedule = youtube_subparsers.add_parser("schedule", help="Set scheduled publish metadata")
    schedule.add_argument("upload_id", type=int, help="YouTube upload ID")
    schedule.add_argument("--publish-at", required=False, help="RFC3339 datetime with timezone")
    schedule.add_argument("--schedule-next", action="store_true", help="Use next default 8:00 PM IST slot")

    upload_list = youtube_subparsers.add_parser("list", help="List YouTube upload records")
    upload_list.add_argument("--status", required=False, help="Filter by upload status")
    upload_list.add_argument("--limit", type=int, default=20, help="Maximum uploads to list")

    upload_show = youtube_subparsers.add_parser("show", help="Show YouTube upload record")
    upload_show.add_argument("upload_id", type=int, help="YouTube upload ID")

    analytics_parser = subparsers.add_parser("analytics", help="YouTube analytics commands")
    analytics_subparsers = analytics_parser.add_subparsers(dest="analytics_command", required=True)

    analytics_fetch = analytics_subparsers.add_parser("fetch", help="Fetch analytics for one upload")
    analytics_fetch.add_argument("upload_id", type=int, help="YouTube upload ID")
    analytics_fetch.add_argument("--mock", action="store_true", help="Use mock analytics")
    analytics_fetch.add_argument(
        "--window",
        choices=["24h", "48h", "7d", "manual"],
        required=False,
        help="Snapshot window override",
    )

    analytics_fetch_all = analytics_subparsers.add_parser("fetch-all", help="Fetch analytics for uploads")
    analytics_fetch_all.add_argument("--mock", action="store_true", help="Use mock analytics")
    analytics_fetch_all.add_argument(
        "--window",
        choices=["24h", "48h", "7d", "manual"],
        required=False,
        help="Snapshot window override",
    )
    analytics_fetch_all.add_argument(
        "--only-due",
        action="store_true",
        help="Fetch only uploads with due 24h/48h/7d snapshots",
    )

    analytics_list = analytics_subparsers.add_parser("list", help="List analytics snapshots")
    analytics_list.add_argument("--status", required=False, help="Filter by snapshot status")
    analytics_list.add_argument("--limit", type=int, default=20, help="Maximum snapshots to list")

    analytics_show = analytics_subparsers.add_parser("show", help="Show analytics snapshot")
    analytics_show.add_argument("snapshot_id", type=int, help="Analytics snapshot ID")

    analytics_subparsers.add_parser("update-scores", help="Update learned category scores")
    analytics_subparsers.add_parser("due", help="List uploads due for analytics snapshots")

    strategy_parser = subparsers.add_parser("strategy", help="Strategy learning commands")
    strategy_subparsers = strategy_parser.add_subparsers(dest="strategy_command", required=True)
    strategy_subparsers.add_parser("recommend", help="Recommend next content distribution")
    strategy_subparsers.add_parser("categories", help="List learned category scores")

    workflow_parser = subparsers.add_parser("workflow", help="Scheduling and operations workflows")
    workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_command", required=True)
    workflow_daily = workflow_subparsers.add_parser("daily-draft", help="Run daily draft workflow")
    workflow_daily.add_argument("--mock", action="store_true", help="Use mock providers")
    workflow_daily.add_argument("--dry-run", action="store_true", help="Record a dry run without generating")
    workflow_subparsers.add_parser("full-mock", help="Run a safe full mock workflow")
    workflow_analytics = workflow_subparsers.add_parser("analytics-due", help="Fetch due analytics snapshots")
    workflow_analytics.add_argument("--mock", action="store_true", help="Use mock analytics")
    workflow_analytics.add_argument("--dry-run", action="store_true", help="Record a dry run without fetching")
    workflow_subparsers.add_parser("status", help="Show operations status")
    workflow_runs = workflow_subparsers.add_parser("runs", help="List workflow runs")
    workflow_runs.add_argument("--type", required=False, help="Filter by workflow type")
    workflow_runs.add_argument("--status", required=False, help="Filter by workflow status")
    workflow_runs.add_argument("--limit", type=int, default=20, help="Maximum runs to list")
    workflow_show = workflow_subparsers.add_parser("show", help="Show a workflow run")
    workflow_show.add_argument("run_id", type=int, help="Workflow run ID")

    review_parser = subparsers.add_parser("review", help="Human review queue commands")
    review_subparsers = review_parser.add_subparsers(dest="review_command", required=True)
    review_subparsers.add_parser("queue", help="Show items needing human action")

    notify_parser = subparsers.add_parser("notify", help="Notification commands")
    notify_subparsers = notify_parser.add_subparsers(dest="notify_command", required=True)
    notify_test = notify_subparsers.add_parser("test", help="Send a test notification")
    notify_test.add_argument("--mock", action="store_true", help="Use mock notifier")

    audit_parser = subparsers.add_parser("audit", help="Audit log commands")
    audit_subparsers = audit_parser.add_subparsers(dest="audit_command", required=True)
    audit_list = audit_subparsers.add_parser("list", help="List audit logs")
    audit_list.add_argument("--action", required=False, help="Filter by action")
    audit_list.add_argument("--entity-type", required=False, help="Filter by entity type")
    audit_list.add_argument("--since", required=False, help="ISO datetime lower bound")
    audit_list.add_argument("--until", required=False, help="ISO datetime upper bound")
    audit_list.add_argument("--limit", type=int, default=20, help="Maximum audit logs")
    audit_list.add_argument("--offset", type=int, default=0, help="Offset for pagination")
    audit_show = audit_subparsers.add_parser("show", help="Show one audit log")
    audit_show.add_argument("id", type=int, help="Audit log ID")
    audit_export_json = audit_subparsers.add_parser("export-json", help="Export audit logs to JSON")
    audit_export_json.add_argument("--action", required=False)
    audit_export_json.add_argument("--entity-type", required=False)
    audit_export_json.add_argument("--since", required=False)
    audit_export_json.add_argument("--until", required=False)
    audit_export_json.add_argument("--limit", type=int, default=500)
    audit_export_csv = audit_subparsers.add_parser("export-csv", help="Export audit logs to CSV")
    audit_export_csv.add_argument("--action", required=False)
    audit_export_csv.add_argument("--entity-type", required=False)
    audit_export_csv.add_argument("--since", required=False)
    audit_export_csv.add_argument("--until", required=False)
    audit_export_csv.add_argument("--limit", type=int, default=500)

    ops_parser = subparsers.add_parser("ops", help="Production operations checks")
    ops_subparsers = ops_parser.add_subparsers(dest="ops_command", required=True)
    ops_subparsers.add_parser("health", help="Show structured operations health")
    ops_subparsers.add_parser("doctor", help="Print deployment safety warnings")
    ops_e2e = ops_subparsers.add_parser("e2e-check", help="Run offline mock end-to-end readiness check")
    ops_e2e.add_argument("--mock", action="store_true", help="Required; do not call real external APIs")

    release_parser = subparsers.add_parser("release", help="Release operations")
    release_subparsers = release_parser.add_subparsers(dest="release_command", required=True)
    release_subparsers.add_parser("status", help="Show release readiness status")
    release_subparsers.add_parser("checklist", help="Print release checklist")
    release_prepare = release_subparsers.add_parser("prepare", help="Prepare a release")
    release_prepare.add_argument("--version", required=True, help="Target release version")
    release_subparsers.add_parser("notes", help="Print release notes")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "db" and args.db_command == "init":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            RaatVerseRepository(session).init_category_scores(settings.all_categories)
        print(f"Database initialized at {settings.database_url}")
        return 0

    if args.command == "db":
        try:
            if args.db_command == "backup":
                path = backup_database(settings)
                print(f"Database backup created: {path}")
                return 0

            if args.db_command == "backups":
                backups = list_backups(settings)
                if not backups:
                    print("No database backups found.")
                    return 0
                for path in backups:
                    print(path)
                return 0

            if args.db_command == "export-json":
                path = export_database_json(settings)
                print(f"Database JSON export created: {path}")
                return 0

            if args.db_command == "import-json":
                if not args.confirm:
                    print("Refusing to import without --confirm.", file=sys.stderr)
                    return 2
                imported = import_database_json(settings, args.path)
                if settings.audit_log_enabled:
                    with session_scope(settings.database_url) as session:
                        RaatVerseRepository(session).create_audit_log(
                            actor="cli",
                            action="db_import_json",
                            entity_type="database",
                            reason="Confirmed JSON import",
                            metadata={"path": args.path, "imported": imported},
                        )
                print("Database JSON import completed:")
                print(json.dumps(imported, indent=2))
                return 0

            if args.db_command == "restore":
                if not args.confirm:
                    print("Refusing to restore without --confirm.", file=sys.stderr)
                    return 2
                path = restore_database(settings, args.backup_path)
                if settings.audit_log_enabled:
                    with session_scope(settings.database_url) as session:
                        RaatVerseRepository(session).create_audit_log(
                            actor="cli",
                            action="db_restore",
                            entity_type="database",
                            reason="Confirmed SQLite restore",
                            metadata={"backup_path": args.backup_path, "restored_to": str(path)},
                        )
                print(f"Database restored to: {path}")
                return 0

            if args.db_command == "status":
                print(json.dumps(database_status(settings), indent=2))
                return 0

            if args.db_command == "migrate":
                create_migration(settings, args.message)
                print("Alembic migration revision created.")
                return 0

            if args.db_command == "upgrade":
                upgrade_database(settings, args.revision)
                print(f"Database upgraded to {args.revision}.")
                return 0

            if args.db_command == "current":
                current_revision(settings)
                return 0

            if args.db_command == "history":
                migration_history(settings)
                return 0

            if args.db_command == "safe-upgrade":
                result = safe_upgrade_database(settings, args.revision)
                print("Database safe upgrade completed.")
                print(json.dumps(result, indent=2, default=str))
                return 0

            if args.db_command == "check-migrations":
                print(json.dumps(check_migrations(settings), indent=2, default=str))
                return 0
        except PersistenceError as exc:
            print(f"Database persistence failed: {exc}", file=sys.stderr)
            return 2
        except MigrationError as exc:
            print(f"Database migration failed: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"Database command failed: {exc}", file=sys.stderr)
            return 2

    if args.command == "pipeline" and args.pipeline_command == "run":
        if not args.mock:
            parser.error("Phase 1 only supports: python -m raatverse_agent pipeline run --mock")

        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            summary = PipelineRunner.mock(settings, repository).run_mock()
        print(format_pipeline_summary(summary))
        return 0

    if args.command == "script":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            repository.init_category_scores(settings.all_categories)

            if args.script_command == "generate":
                request = ScriptGenerationRequest(
                    category=args.category if not args.auto_category or args.category else None,
                    story_type=args.story_type,
                    seed=args.seed,
                    mock=args.mock,
                    auto_category=args.auto_category,
                )
                try:
                    generator = create_script_draft_generator(settings, mock=args.mock)
                    service = ScriptDraftService(
                        settings=settings,
                        repository=repository,
                        generator=generator,
                    )
                    response = service.generate(request)
                except (LLMConfigurationError, LLMProviderError, ValueError) as exc:
                    print(f"Script generation failed: {exc}", file=sys.stderr)
                    return 2

                print(format_script_generation_response(response))
                return 0 if response.draft is not None else 2

            if args.script_command == "list":
                drafts = repository.list_script_drafts(status=args.status, limit=args.limit)
                if not drafts:
                    print("No script drafts found.")
                    return 0
                for draft in drafts:
                    print(
                        f"{draft.id}: [{draft.status}] {draft.category}/{draft.story_type} - {draft.title}"
                    )
                return 0

            if args.script_command == "show":
                draft = repository.get_script_draft(args.id)
                if draft is None:
                    print(f"Script draft {args.id} was not found.", file=sys.stderr)
                    return 1
                print(format_script_draft(draft))
                return 0

            if args.script_command == "approve":
                before = repository.get_script_draft(args.id)
                draft = repository.update_script_draft_status(args.id, "approved")
                if draft is None:
                    print(f"Script draft {args.id} was not found.", file=sys.stderr)
                    return 1
                if settings.audit_log_enabled:
                    repository.create_audit_log(
                        actor="cli",
                        action="script_approve",
                        entity_type="script_draft",
                        entity_id=draft.id,
                        before_status=before.status if before else None,
                        after_status=draft.status,
                        reason=args.comment,
                    )
                    repository.create_approval_event(
                        actor="cli",
                        entity_type="script_draft",
                        entity_id=draft.id,
                        action="script_approve",
                        comment=args.comment,
                    )
                print(f"Approved script draft {draft.id}: {draft.title}")
                return 0

            if args.script_command == "reject":
                before = repository.get_script_draft(args.id)
                draft = repository.update_script_draft_status(args.id, "rejected", args.reason)
                if draft is None:
                    print(f"Script draft {args.id} was not found.", file=sys.stderr)
                    return 1
                if settings.audit_log_enabled:
                    repository.create_audit_log(
                        actor="cli",
                        action="script_reject",
                        entity_type="script_draft",
                        entity_id=draft.id,
                        before_status=before.status if before else None,
                        after_status=draft.status,
                        reason=args.reason,
                        metadata={"comment": args.comment} if args.comment else None,
                    )
                    repository.create_approval_event(
                        actor="cli",
                        entity_type="script_draft",
                        entity_id=draft.id,
                        action="script_reject",
                        comment=args.comment or args.reason,
                    )
                print(f"Rejected script draft {draft.id}: {draft.title}")
                return 0

            if args.script_command == "regenerate":
                try:
                    generator = create_script_draft_generator(settings, mock=args.mock)
                    service = ScriptDraftService(
                        settings=settings,
                        repository=repository,
                        generator=generator,
                    )
                    response = service.regenerate_rejected(args.id)
                except (LLMConfigurationError, LLMProviderError, ValueError) as exc:
                    print(f"Script regeneration failed: {exc}", file=sys.stderr)
                    return 2
                print(format_script_generation_response(response))
                if settings.audit_log_enabled and response.saved_draft_id is not None:
                    repository.create_audit_log(
                        actor="cli",
                        action="script_regenerate",
                        entity_type="script_draft",
                        entity_id=args.id,
                        metadata={"new_script_id": response.saved_draft_id, "mock": args.mock},
                    )
                    repository.create_approval_event(
                        actor="cli",
                        entity_type="script_draft",
                        entity_id=args.id,
                        action="script_regenerate",
                        comment=f"New draft: {response.saved_draft_id}",
                    )
                return 0 if response.draft is not None else 2

    if args.command == "tts":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            if args.tts_command == "generate":
                try:
                    service = create_tts_asset_service(
                        settings=settings,
                        repository=repository,
                        mock=args.mock,
                    )
                    audio = service.generate_for_script(
                        args.script_id,
                        TTSGenerationRequest(mock=args.mock, force=args.force),
                    )
                except (AssetWorkflowError, ValueError) as exc:
                    print(f"TTS generation failed: {exc}", file=sys.stderr)
                    return 2
                print(format_audio_asset(audio))
                return 0 if audio.status == "asset_ready" else 2

    if args.command == "assets":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            if args.assets_command == "prepare":
                try:
                    service = create_asset_preparation_service(
                        settings=settings,
                        repository=repository,
                        mock=args.mock,
                    )
                    plan = service.prepare_for_script(
                        args.script_id,
                        AssetPreparationRequest(
                            mock=args.mock,
                            force=args.force,
                            download_enabled=True if args.download else None,
                        ),
                    )
                except (AssetWorkflowError, ValueError) as exc:
                    print(f"Asset preparation failed: {exc}", file=sys.stderr)
                    return 2
                if settings.audit_log_enabled:
                    repository.create_audit_log(
                        actor="cli",
                        action="assets_prepare",
                        entity_type="asset_plan",
                        entity_id=plan.id,
                        after_status=plan.status,
                        reason=args.note,
                        metadata={"script_id": args.script_id, "mock": args.mock},
                    )
                    repository.create_approval_event(
                        actor="cli",
                        entity_type="asset_plan",
                        entity_id=plan.id,
                        action="assets_prepare",
                        comment=args.note,
                    )
                print(format_asset_plan(plan))
                print()
                draft = repository.get_script_draft(plan.script_draft_id)
                print(format_asset_quality_report(analyze_asset_plan(plan, settings, draft)))
                return 0 if plan.status == "asset_ready" else 2

            if args.assets_command == "list":
                plans = repository.list_asset_plans(status=args.status, limit=args.limit)
                if not plans:
                    print("No asset plans found.")
                    return 0
                for plan in plans:
                    print(
                        f"{plan.id}: [{plan.status}] script={plan.script_draft_id} "
                        f"audio={plan.audio_asset_id} media={len(plan.media_assets)} provider={plan.provider}"
                    )
                return 0

            if args.assets_command == "show":
                plan = repository.get_asset_plan(args.id)
                if plan is None:
                    print(f"Asset plan {args.id} was not found.", file=sys.stderr)
                    return 1
                print(format_asset_plan(plan))
                return 0

            if args.assets_command == "quality":
                plan = repository.get_asset_plan(args.id)
                if plan is None:
                    print(f"Asset plan {args.id} was not found.", file=sys.stderr)
                    return 1
                draft = repository.get_script_draft(plan.script_draft_id)
                print(format_asset_quality_report(analyze_asset_plan(plan, settings, draft)))
                return 0

    if args.command == "render":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            if args.render_command == "create":
                try:
                    service = create_render_workflow_service(
                        settings=settings,
                        repository=repository,
                        mock=args.mock,
                    )
                    render = service.create_render(
                        args.asset_plan_id,
                        RenderRequest(
                            mock=args.mock,
                            force=args.force,
                            strict_quality=args.strict_quality,
                        ),
                    )
                except (RenderWorkflowError, ValueError) as exc:
                    print(f"Render failed: {exc}", file=sys.stderr)
                    return 2
                if settings.audit_log_enabled:
                    repository.create_audit_log(
                        actor="cli",
                        action="render_create",
                        entity_type="video_render",
                        entity_id=render.id,
                        after_status=render.status,
                        reason=args.note,
                        metadata={"asset_plan_id": args.asset_plan_id, "mock": args.mock},
                    )
                    repository.create_approval_event(
                        actor="cli",
                        entity_type="video_render",
                        entity_id=render.id,
                        action="render_create",
                        comment=args.note,
                    )
                print(format_video_render(render))
                return 0 if render.status == "render_ready" else 2

            if args.render_command == "list":
                renders = repository.list_video_renders(status=args.status, limit=args.limit)
                if not renders:
                    print("No video renders found.")
                    return 0
                for render in renders:
                    print(
                        f"{render.id}: [{render.status}] asset_plan={render.asset_plan_id} "
                        f"provider={render.renderer_provider} output={render.output_path or 'None'}"
                    )
                return 0

            if args.render_command == "show":
                render = repository.get_video_render(args.id)
                if render is None:
                    print(f"Video render {args.id} was not found.", file=sys.stderr)
                    return 1
                print(format_video_render(render))
                return 0

            if args.render_command == "validate":
                try:
                    service = create_render_workflow_service(
                        settings=settings,
                        repository=repository,
                        mock=True,
                    )
                    result = service.validate_asset_plan(
                        args.asset_plan_id,
                        force=args.force,
                        strict_quality=args.strict_quality,
                    )
                except ValueError as exc:
                    print(f"Render validation failed: {exc}", file=sys.stderr)
                    return 2
                print(format_render_validation(result))
                return 0 if result.is_valid else 2

    if args.command == "youtube":
        if args.youtube_command == "oauth-url":
            try:
                print(build_oauth_url(settings))
            except YouTubeOAuthError as exc:
                print(f"YouTube OAuth URL failed: {exc}", file=sys.stderr)
                return 2
            return 0

        if args.youtube_command == "exchange-code":
            try:
                exchange_code_for_token(settings, args.code)
            except YouTubeOAuthError as exc:
                print(f"YouTube OAuth exchange failed: {exc}", file=sys.stderr)
                return 2
            print(f"YouTube token saved to {settings.youtube_token_file}")
            return 0

        if args.youtube_command == "token-status":
            print(format_token_status(token_status(settings)))
            return 0

        if args.youtube_command == "revoke-local-token":
            removed = revoke_local_token(settings)
            print("Local YouTube token deleted." if removed else "No local YouTube token file found.")
            return 0

        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            try:
                if args.youtube_command == "metadata-preview":
                    service = create_youtube_upload_service(
                        settings=settings,
                        repository=repository,
                        mock=True,
                    )
                    metadata = service.metadata_preview(args.render_id)
                    print(format_metadata_preview(metadata))
                    return 0

                if args.youtube_command == "prepare-upload":
                    service = create_youtube_upload_service(
                        settings=settings,
                        repository=repository,
                        mock=True,
                    )
                    upload = service.prepare_upload(args.render_id)
                    if settings.audit_log_enabled:
                        repository.create_audit_log(
                            actor="cli",
                            action="youtube_prepare_upload",
                            entity_type="youtube_upload",
                            entity_id=upload.id,
                            after_status=upload.status,
                            reason=args.note,
                            metadata={"render_id": args.render_id},
                        )
                        repository.create_approval_event(
                            actor="cli",
                            entity_type="youtube_upload",
                            entity_id=upload.id,
                            action="youtube_prepare_upload",
                            comment=args.note,
                        )
                    print(format_youtube_upload(upload))
                    return 0

                if args.youtube_command == "approve-upload":
                    before = repository.get_youtube_upload(args.upload_id)
                    service = create_youtube_upload_service(
                        settings=settings,
                        repository=repository,
                        mock=True,
                    )
                    upload = service.approve_upload(args.upload_id)
                    if settings.audit_log_enabled:
                        repository.create_audit_log(
                            actor="cli",
                            action="youtube_approve_upload",
                            entity_type="youtube_upload",
                            entity_id=upload.id,
                            before_status=before.status if before else None,
                            after_status=upload.status,
                            reason=args.comment,
                        )
                        repository.create_approval_event(
                            actor="cli",
                            entity_type="youtube_upload",
                            entity_id=upload.id,
                            action="youtube_approve_upload",
                            comment=args.comment,
                        )
                    print(format_youtube_upload(upload))
                    return 0

                if args.youtube_command == "schedule":
                    service = create_youtube_upload_service(
                        settings=settings,
                        repository=repository,
                        mock=True,
                    )
                    upload = service.schedule_upload(
                        args.upload_id,
                        YouTubeScheduleRequest(
                            publish_at=args.publish_at,
                            schedule_next=args.schedule_next,
                        ),
                    )
                    print(format_youtube_upload(upload))
                    return 0

                if args.youtube_command == "upload":
                    before = repository.get_youtube_upload(args.upload_id)
                    service = create_youtube_upload_service(
                        settings=settings,
                        repository=repository,
                        mock=args.mock,
                    )
                    upload = service.upload(
                        args.upload_id,
                        YouTubeUploadRequest(mock=args.mock, approve_now=args.approve_now),
                    )
                    if settings.audit_log_enabled:
                        repository.create_audit_log(
                            actor="cli",
                            action="youtube_upload_attempt",
                            entity_type="youtube_upload",
                            entity_id=upload.id,
                            before_status=before.status if before else None,
                            after_status=upload.status,
                            metadata={"mock": args.mock, "approve_now": args.approve_now},
                        )
                    print(format_youtube_upload(upload))
                    return 0 if upload.status in {"upload_private", "upload_scheduled"} else 2

                if args.youtube_command == "list":
                    uploads = repository.list_youtube_uploads(status=args.status, limit=args.limit)
                    if not uploads:
                        print("No YouTube upload records found.")
                        return 0
                    for upload in uploads:
                        print(
                            f"{upload.id}: [{upload.status}] render={upload.video_render_id} "
                            f"privacy={upload.privacy_status} url={upload.youtube_url or 'None'}"
                        )
                    return 0

                if args.youtube_command == "show":
                    upload = repository.get_youtube_upload(args.upload_id)
                    if upload is None:
                        print(f"YouTube upload {args.upload_id} was not found.", file=sys.stderr)
                        return 1
                    print(format_youtube_upload(upload))
                    return 0
            except (YouTubeWorkflowError, ValueError) as exc:
                print(f"YouTube workflow failed: {exc}", file=sys.stderr)
                return 2

    if args.command == "analytics":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            try:
                if args.analytics_command == "fetch":
                    service = create_analytics_workflow_service(
                        settings=settings,
                        repository=repository,
                        mock=args.mock,
                    )
                    snapshot = service.fetch_for_upload(
                        args.upload_id,
                        AnalyticsFetchRequest(
                            mock=args.mock,
                            snapshot_window=args.window,
                        ),
                    )
                    print(format_analytics_snapshot(snapshot))
                    return 0 if snapshot.status != "snapshot_failed" else 2

                if args.analytics_command == "fetch-all":
                    service = create_analytics_workflow_service(
                        settings=settings,
                        repository=repository,
                        mock=args.mock,
                    )
                    snapshots = service.fetch_all(
                        AnalyticsFetchAllRequest(
                            mock=args.mock,
                            snapshot_window=args.window,
                            only_due=args.only_due,
                        )
                    )
                    if not snapshots:
                        print("No uploaded YouTube records found for analytics fetch.")
                        return 0
                    for snapshot in snapshots:
                        print(format_analytics_snapshot(snapshot))
                        print()
                    return 0 if all(snapshot.status != "snapshot_failed" for snapshot in snapshots) else 2

                if args.analytics_command == "list":
                    snapshots = repository.list_analytics_snapshots(status=args.status, limit=args.limit)
                    if not snapshots:
                        print("No analytics snapshots found.")
                        return 0
                    for snapshot in snapshots:
                        print(
                            f"{snapshot.id}: [{snapshot.status}] upload={snapshot.youtube_upload_id} "
                            f"window={snapshot.snapshot_window} views={snapshot.views} "
                            f"score={snapshot.performance_score:.2f}"
                        )
                    return 0

                if args.analytics_command == "show":
                    snapshot = repository.get_analytics_snapshot(args.snapshot_id)
                    if snapshot is None:
                        print(f"Analytics snapshot {args.snapshot_id} was not found.", file=sys.stderr)
                        return 1
                    print(format_analytics_snapshot(snapshot))
                    return 0

                if args.analytics_command == "update-scores":
                    scores = StrategyLearningService(
                        settings=settings,
                        repository=repository,
                    ).update_category_scores()
                    if not scores:
                        print("No analytics snapshots available for category scoring.")
                        return 0
                    for score in scores:
                        print(format_category_score(score))
                    return 0

                if args.analytics_command == "due":
                    service = create_analytics_workflow_service(
                        settings=settings,
                        repository=repository,
                        mock=True,
                    )
                    print(format_due_snapshots(service.due_snapshots()))
                    return 0
            except (AnalyticsWorkflowError, ValueError) as exc:
                print(f"Analytics workflow failed: {exc}", file=sys.stderr)
                return 2

    if args.command == "strategy":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            repository.init_category_scores(settings.all_categories)
            service = StrategyLearningService(settings=settings, repository=repository)
            if args.strategy_command == "recommend":
                print(format_strategy_recommendation(service.recommend()))
                return 0
            if args.strategy_command == "categories":
                scores = service.categories()
                if not scores:
                    print("No category scores found.")
                    return 0
                for score in scores:
                    print(format_category_score(score))
                return 0

    if args.command == "workflow":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            repository.init_category_scores(settings.all_categories)
            service = WorkflowOrchestrationService(settings=settings, repository=repository)

            if args.workflow_command == "daily-draft":
                run = service.run_daily_draft(
                    WorkflowRequest(mock=args.mock, dry_run=args.dry_run)
                )
                if settings.audit_log_enabled:
                    repository.create_audit_log(
                        actor="cli",
                        action="workflow_run_triggered",
                        entity_type="workflow_run",
                        entity_id=run.id,
                        after_status=run.status,
                        metadata={"workflow_type": run.workflow_type, "mock": args.mock},
                    )
                print(format_workflow_run(run))
                return 0 if run.status in {"success", "skipped"} else 2

            if args.workflow_command == "full-mock":
                run = service.run_full_mock()
                if settings.audit_log_enabled:
                    repository.create_audit_log(
                        actor="cli",
                        action="workflow_run_triggered",
                        entity_type="workflow_run",
                        entity_id=run.id,
                        after_status=run.status,
                        metadata={"workflow_type": run.workflow_type, "mock": True},
                    )
                print(format_workflow_run(run))
                return 0 if run.status == "success" else 2

            if args.workflow_command == "analytics-due":
                run = service.run_analytics_due(
                    WorkflowRequest(mock=args.mock, dry_run=args.dry_run)
                )
                if settings.audit_log_enabled:
                    repository.create_audit_log(
                        actor="cli",
                        action="workflow_run_triggered",
                        entity_type="workflow_run",
                        entity_id=run.id,
                        after_status=run.status,
                        metadata={"workflow_type": run.workflow_type, "mock": args.mock},
                    )
                print(format_workflow_run(run))
                return 0 if run.status in {"success", "skipped"} else 2

            if args.workflow_command == "status":
                print(format_ops_status(service.status()))
                return 0

            if args.workflow_command == "runs":
                runs = repository.list_workflow_runs(
                    workflow_type=args.type,
                    status=args.status,
                    limit=args.limit,
                )
                if not runs:
                    print("No workflow runs found.")
                    return 0
                for run in runs:
                    print(
                        f"{run.id}: [{run.status}] {run.workflow_type} "
                        f"mode={run.provider_mode} script={run.created_script_id or 'None'}"
                    )
                return 0

            if args.workflow_command == "show":
                run = repository.get_workflow_run(args.run_id)
                if run is None:
                    print(f"Workflow run {args.run_id} was not found.", file=sys.stderr)
                    return 1
                print(format_workflow_run(run))
                return 0

    if args.command == "review":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            service = WorkflowOrchestrationService(settings=settings, repository=repository)
            if args.review_command == "queue":
                print(format_review_queue(service.review_queue()))
                return 0

    if args.command == "audit":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            if args.audit_command == "list":
                if args.since or args.until:
                    logs = filtered_audit_logs(
                        repository,
                        action=args.action,
                        entity_type=args.entity_type,
                        since=args.since,
                        until=args.until,
                        limit=args.limit,
                    )
                else:
                    logs = repository.list_audit_logs(
                        action=args.action,
                        entity_type=args.entity_type,
                        limit=args.limit,
                        offset=args.offset,
                    )
                if not logs:
                    print("No audit logs found.")
                    return 0
                for log in logs:
                    print(format_audit_log_line(log))
                return 0

            if args.audit_command == "show":
                log = repository.get_audit_log(args.id)
                if log is None:
                    print(f"Audit log {args.id} was not found.", file=sys.stderr)
                    return 1
                print(format_audit_log(log))
                return 0

            if args.audit_command == "export-json":
                logs = filtered_audit_logs(
                    repository,
                    action=args.action,
                    entity_type=args.entity_type,
                    since=args.since,
                    until=args.until,
                    limit=args.limit,
                )
                path = export_audit_json(settings, logs)
                print(f"Audit JSON export created: {path}")
                return 0

            if args.audit_command == "export-csv":
                logs = filtered_audit_logs(
                    repository,
                    action=args.action,
                    entity_type=args.entity_type,
                    since=args.since,
                    until=args.until,
                    limit=args.limit,
                )
                path = export_audit_csv(settings, logs)
                print(f"Audit CSV export created: {path}")
                return 0

    if args.command == "ops":
        initialize_database(settings.database_url)
        with session_scope(settings.database_url) as session:
            repository = RaatVerseRepository(session)
            service = WorkflowOrchestrationService(settings=settings, repository=repository)
            queue = service.review_queue()
            latest_runs = repository.list_workflow_runs(limit=1)
            health = ops_health_payload(
                settings=settings,
                queue=queue,
                latest_workflow_run=latest_runs[0] if latest_runs else None,
            )
            if args.ops_command == "health":
                print(format_ops_health(health))
                return 0
            if args.ops_command == "doctor":
                print(format_ops_doctor(health))
                return 0
            if args.ops_command == "e2e-check":
                if not args.mock:
                    print("E2E check is mock-only; pass --mock.", file=sys.stderr)
                    return 2
                result = run_e2e_check(settings=settings, repository=repository, mock=True)
                print(format_e2e_check(result))
                return 0 if result["status"] in {"ok", "warning"} else 2

    if args.command == "release":
        if args.release_command == "status":
            print(format_release_status(release_status(settings)))
            return 0
        if args.release_command == "checklist":
            print(format_release_checklist(release_checklist()))
            return 0
        if args.release_command == "prepare":
            print(format_release_prepare(prepare_release(settings, args.version)))
            return 0
        if args.release_command == "notes":
            print(release_notes())
            return 0

    if args.command == "notify":
        if args.notify_command == "test":
            try:
                result = NotificationService(settings).event(
                    event="test",
                    title="RaatVerse notification test",
                    body="This is a test notification from the local RaatVerse agent.",
                    data={"channel": settings.channel_name},
                    mock=args.mock,
                    force=True,
                )
            except NotificationError as exc:
                print(f"Notification failed: {exc}", file=sys.stderr)
                return 2
            print(format_notification_result(result))
            return 0 if result.sent else 2

    parser.print_help()
    return 1
