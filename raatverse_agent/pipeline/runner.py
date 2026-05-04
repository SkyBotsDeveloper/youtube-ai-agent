from __future__ import annotations

from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.pipeline.models import PipelineSummary, StoryIdeaResult
from raatverse_agent.services.interfaces import (
    ScriptGenerator,
    StrategyAgent,
    ThumbnailGenerator,
    VideoRenderer,
    VisualProvider,
    VoiceGenerator,
    YouTubeUploader,
)
from raatverse_agent.services.mock import (
    MockScriptGenerator,
    MockStrategyAgent,
    MockThumbnailGenerator,
    MockVideoRenderer,
    MockVisualProvider,
    MockVoiceGenerator,
    MockYouTubeUploader,
)


class PipelineRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RaatVerseRepository,
        strategy_agent: StrategyAgent,
        script_generator: ScriptGenerator,
        visual_provider: VisualProvider,
        voice_generator: VoiceGenerator,
        video_renderer: VideoRenderer,
        thumbnail_generator: ThumbnailGenerator,
        youtube_uploader: YouTubeUploader,
    ):
        self.settings = settings
        self.repository = repository
        self.strategy_agent = strategy_agent
        self.script_generator = script_generator
        self.visual_provider = visual_provider
        self.voice_generator = voice_generator
        self.video_renderer = video_renderer
        self.thumbnail_generator = thumbnail_generator
        self.youtube_uploader = youtube_uploader

    @classmethod
    def mock(cls, settings: Settings, repository: RaatVerseRepository) -> "PipelineRunner":
        return cls(
            settings=settings,
            repository=repository,
            strategy_agent=MockStrategyAgent(),
            script_generator=MockScriptGenerator(),
            visual_provider=MockVisualProvider(settings.stock_media_provider),
            voice_generator=MockVoiceGenerator(settings),
            video_renderer=MockVideoRenderer(settings),
            thumbnail_generator=MockThumbnailGenerator(),
            youtube_uploader=MockYouTubeUploader(settings),
        )

    def run_mock(self) -> PipelineSummary:
        run = self.repository.start_pipeline_run(mode="mock")
        try:
            self.repository.init_category_scores(self.settings.story_categories)
            category_scores = self.repository.get_category_score_states()
            category = self.strategy_agent.choose_category(
                self.settings.story_categories,
                category_scores,
            )

            premise = (
                "A compact Hindi/Hinglish suspense story with a cinematic horror setup, "
                "one emotional reveal, and a clean subscriber CTA."
            )
            idea = self.repository.create_story_idea(
                category=category,
                seed=f"mock-seed-{run.run_uid[:8]}",
                premise=premise,
            )
            idea_result = StoryIdeaResult(
                idea_uid=idea.idea_uid,
                category=category,
                seed=idea.seed,
                premise=idea.premise,
                target_duration_seconds=self.settings.target_duration_seconds,
            )

            script = self.script_generator.generate(idea_result, self.settings.outro_cta)
            visuals = self.visual_provider.find_assets(script)
            voiceover = self.voice_generator.generate(script)
            render = self.video_renderer.render(script, visuals, voiceover)
            thumbnail = self.thumbnail_generator.generate(script)
            upload = self.youtube_uploader.prepare_upload(script, render, thumbnail)

            self.repository.create_video(
                title=script.title,
                category=category,
                script_text=script.script,
                duration_seconds=script.estimated_duration_seconds,
                privacy_status=upload.privacy_status,
            )
            self.repository.bump_category_upload(category)

            summary = PipelineSummary(
                run_uid=run.run_uid,
                status="completed",
                category=category,
                title=script.title,
                script_excerpt=script.script[:240],
                visual_assets=visuals,
                voiceover=voiceover,
                render=render,
                thumbnail=thumbnail,
                upload=upload,
                next_action="Review the mock plan. Real upload remains disabled in Phase 1.",
            )
            self.repository.complete_pipeline_run(
                run,
                category=category,
                summary=summary.model_dump(mode="json"),
            )
            return summary
        except Exception as exc:
            self.repository.fail_pipeline_run(run, str(exc))
            raise
