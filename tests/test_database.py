from sqlalchemy import inspect

from raatverse_agent.db.session import initialize_database


def test_database_initialization_creates_expected_tables(tmp_path):
    db_file = tmp_path / "raatverse.db"
    engine = initialize_database(f"sqlite:///{db_file.as_posix()}")

    table_names = set(inspect(engine).get_table_names())

    assert {
        "videos",
        "story_ideas",
        "analytics_snapshots",
        "category_scores",
        "pipeline_runs",
        "script_drafts",
        "audio_assets",
        "asset_plans",
        "video_renders",
        "youtube_uploads",
        "workflow_runs",
    }.issubset(table_names)
