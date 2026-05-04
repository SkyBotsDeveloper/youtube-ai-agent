from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.pipeline.runner import PipelineRunner


def test_mock_pipeline_execution_persists_run(tmp_path):
    db_file = tmp_path / "pipeline.db"
    settings = Settings(
        database_url=f"sqlite:///{db_file.as_posix()}",
        story_categories_csv="haunted-room,train-mystery",
        output_dir=str(tmp_path / "outputs"),
    )

    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        summary = PipelineRunner.mock(settings, repository).run_mock()
        runs = repository.list_pipeline_runs()

    assert summary.status == "completed"
    assert summary.category in settings.story_categories
    assert summary.upload.privacy_status == "private"
    assert summary.render.resolution == "1080x1920"
    assert len(summary.visual_assets) >= 1
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
