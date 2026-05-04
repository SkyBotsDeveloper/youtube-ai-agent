from __future__ import annotations

from hashlib import md5
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from raatverse_agent.config import Settings
from raatverse_agent.pipeline.models import (
    AnalyticsSnapshotResult,
    CategoryScoreState,
    RenderMetadata,
    ScriptResult,
    StoryIdeaResult,
    ThumbnailMetadata,
    UploadMetadata,
    VisualAssetRef,
    VoiceoverMetadata,
)
from raatverse_agent.script_generation.models import (
    ScriptDraft,
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    ScriptSceneBeat,
    ScriptValidationResult,
)
from raatverse_agent.script_generation.prompts import (
    PROMPT_VERSION,
    get_prompt_template,
    normalize_category,
)
from raatverse_agent.services.interfaces import (
    AnalyticsFetcher,
    ScriptDraftGenerator,
    ScriptGenerator,
    StrategyAgent,
    ThumbnailGenerator,
    VideoRenderer,
    VisualProvider,
    VoiceGenerator,
    YouTubeUploader,
)


def _display_category(category: str) -> str:
    return category.replace("-", " ").title()


class MockStrategyAgent(StrategyAgent):
    """Deterministic placeholder strategy for daily category rotation."""

    def choose_category(
        self,
        categories: Sequence[str],
        category_scores: Sequence[CategoryScoreState],
    ) -> str:
        if not categories:
            raise ValueError("At least one story category is required.")

        score_by_category = {score.category: score for score in category_scores}
        order_by_category = {category: index for index, category in enumerate(categories)}

        def rank(category: str) -> tuple[int, float, int]:
            state = score_by_category.get(category)
            if state is None:
                return (0, 0.0, order_by_category[category])
            return (state.uploads, -state.score, order_by_category[category])

        return sorted(categories, key=rank)[0]

    def score_category_performance(self, views: int, likes: int, uploads: int) -> float:
        if uploads <= 0:
            return 0.0
        engagement_value = views + (likes * 5)
        return round(engagement_value / uploads, 2)


class MockScriptGenerator(ScriptGenerator):
    def generate(self, idea: StoryIdeaResult, outro_cta: str) -> ScriptResult:
        category_name = _display_category(idea.category)
        title = f"{category_name}: Raat 2:17 Ka Raaz"
        hook = "Raat ke 2:17 baje, phone apne aap record hone laga."
        script = (
            f"{hook}\n"
            f"Aarav ne screen dekhi, par camera uske kamre ko nahi, ek purani haveli ke darwaze ko dikha raha tha. "
            f"Darwaze par wahi naam likha tha jo uski dadi sirf sapno mein leti thi. "
            f"Jab usne volume badhaya, andar se uski hi awaaz aayi: 'mat kholo'. "
            f"Phir mirror mein ek parchai ruki, aur phone par message flash hua: 'kal raat tum wapas aaye the'. "
            f"Subah Aarav ke phone mein ek nayi video thi, jisme woh khud us haveli ke andar khada tha. "
            f"{outro_cta}"
        )
        return ScriptResult(
            title=title,
            hook=hook,
            script=script,
            category=idea.category,
            estimated_duration_seconds=idea.target_duration_seconds,
            outro_cta=outro_cta,
        )


class MockDraftScriptGenerator(ScriptDraftGenerator):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_draft(self, request: ScriptGenerationRequest) -> ScriptGenerationResponse:
        category = normalize_category(request.category or self.settings.script_categories[0])
        template = get_prompt_template(category)
        story_type = request.story_type or template["story_type"]
        language_style = request.language_style or self.settings.language_style
        duration = request.target_duration_seconds or self.settings.target_duration_seconds
        build_end = max(25, min(35, duration - 18))
        reveal_end = max(build_end + 8, duration - 7)
        seed = request.seed or "mirror message"
        variant = md5(seed.encode("utf-8")).hexdigest()[:4] if request.seed else ""
        title = (
            f"{_display_category(category)}: Naya Sanket {variant}"
            if variant
            else f"{_display_category(category)}: Aakhri Message"
        )
        minute = 17 + (int(variant[:1], 16) % 5 if variant else 0)
        hook = f"Raat ke 2:{minute:02d} baje, Meera ke phone par uski hi awaaz ka message aaya."
        narration = (
            f"{hook} "
            "Message sirf teen shabdon ka tha: darwaza mat khol. "
            "Meera ne corridor ki light on ki, par bulb jalte hi diwar par geeli mitti ke nishaan dikhne lage. "
            f"Usne socha yeh koi prank hoga, lekin har nishaan uske kamre ki taraf aa raha tha. "
            "Phone par doosra audio play hua: Meera, agar tu mujhe sun rahi hai, main kal wali tu hoon. "
            "Tabhi almari ke sheeshe mein usne apna reflection dekha, par reflection ke haath mein ek purani chabi thi. "
            "Chabi par us ghar ka number likha tha jahan woh bachpan mein kabhi gayi hi nahi thi. "
            "Subah police ko corridor mein sirf mitti mili, aur Meera ke phone mein ek nayi recording: "
            "aaj raat main wapas aaungi, par is baar darwaza tum kholna. "
            f"{self.settings.outro_cta}"
        )
        tts_narration = (
            f"रात के 2:{minute:02d} बजे, मीरा के फोन पर उसी की आवाज का मैसेज आया। "
            "मैसेज सिर्फ तीन शब्दों का था: दरवाजा मत खोल। "
            "मीरा ने कॉरिडोर की लाइट ऑन की, पर बल्ब जलते ही दीवार पर गीली मिट्टी के निशान दिखने लगे। "
            "उसने सोचा यह कोई प्रैंक होगा, लेकिन हर निशान उसके कमरे की तरफ आ रहा था। "
            "फोन पर दूसरा ऑडियो प्ले हुआ: मीरा, अगर तू मुझे सुन रही है, मैं कल वाली तू हूं। "
            "तभी अलमारी के शीशे में उसने अपना रिफ्लेक्शन देखा, पर रिफ्लेक्शन के हाथ में एक पुरानी चाबी थी। "
            "चाबी पर उस घर का नंबर लिखा था जहां वह बचपन में कभी गई ही नहीं थी। "
            "सुबह पुलिस को कॉरिडोर में सिर्फ मिट्टी मिली, और मीरा के फोन में एक नई रिकॉर्डिंग थी: "
            "आज रात मैं वापस आऊंगी, पर इस बार दरवाजा तुम खोलना। "
            "अगर कहानी पसंद आई हो, तो रातवर्स को सब्सक्राइब करो। कल रात एक और नई कहानी मिलेगी।"
        )
        draft = ScriptDraft(
            title=title,
            category=category,
            story_type=story_type,
            hook=hook,
            full_narration_script=narration,
            narration_hindi_devanagari_for_tts=tts_narration,
            scene_beats=[
                ScriptSceneBeat(
                    start_second=0,
                    end_second=3,
                    narration=hook,
                    visual_suggestion="Extreme close-up of a phone glowing in a dark room.",
                    narration_segment=hook,
                    stock_search_query="phone screen glowing dark room night vertical horror close up",
                    negative_keywords=["cartoon", "bright daylight", "comedy"],
                    mood="eerie",
                    location="dark bedroom",
                    camera_motion="static close-up",
                ),
                ScriptSceneBeat(
                    start_second=3,
                    end_second=build_end,
                    narration="Meera follows wet footprints through a quiet corridor.",
                    visual_suggestion="Slow vertical dolly through a dim corridor with wet floor marks.",
                    narration_segment="Message warns Meera not to open the door while wet footprints move through the corridor.",
                    stock_search_query="dark narrow corridor wet floor footprints night vertical suspense",
                    negative_keywords=["crowd", "bright office", "sunny"],
                    mood="slow suspense",
                    location="dim corridor",
                    camera_motion="slow dolly",
                ),
                ScriptSceneBeat(
                    start_second=build_end,
                    end_second=reveal_end,
                    narration="The reflection reveals a key and a message from tomorrow.",
                    visual_suggestion="Mirror reflection holding an old key while the real hand is empty.",
                    narration_segment="The mirror shows a key in the reflection and a message from tomorrow.",
                    stock_search_query="old mirror reflection key dark room cinematic vertical",
                    negative_keywords=["makeup tutorial", "bright bathroom", "happy"],
                    mood="uncanny reveal",
                    location="old mirror in dark room",
                    camera_motion="slow push-in",
                ),
                ScriptSceneBeat(
                    start_second=reveal_end,
                    end_second=duration,
                    narration=self.settings.outro_cta,
                    visual_suggestion="RaatVerse title over dark cinematic texture.",
                    narration_segment=self.settings.outro_cta,
                    stock_search_query="dark cinematic smoke texture black background vertical",
                    negative_keywords=["logo", "cartoon", "bright"],
                    mood="premium outro",
                    location="abstract dark texture",
                    camera_motion="slow pan",
                ),
            ],
            subtitle_lines=[
                "Raat ke 2:17 baje phone baja.",
                "Message uski hi awaaz mein tha.",
                "Darwaza mat khol.",
                "Kal wali Meera wapas aa gayi thi.",
            ],
            cta_line=self.settings.outro_cta,
            estimated_duration_seconds=duration,
            language_style=language_style,
            safety_notes=["Suspenseful and non-graphic; no real-person claims."],
            originality_notes=[f"Fresh mock premise using seed: {seed}."],
            provider="mock",
            prompt_version=PROMPT_VERSION,
        )
        return ScriptGenerationResponse(
            draft=draft,
            validation=ScriptValidationResult.ok(),
            provider="mock",
            raw_response=None,
        )


class MockVisualProvider(VisualProvider):
    def __init__(self, provider_name: str = "mock-stock"):
        self.provider_name = provider_name

    def find_assets(self, script: ScriptResult) -> list[VisualAssetRef]:
        base = _display_category(script.category).lower()
        return [
            VisualAssetRef(
                provider=self.provider_name,
                query=f"{base} dark cinematic corridor vertical",
                duration_seconds=12,
                license_note="Mock reference only; replace with licensed stock media.",
            ),
            VisualAssetRef(
                provider=self.provider_name,
                query="old haveli door night fog vertical",
                duration_seconds=14,
                license_note="Mock reference only; replace with licensed stock media.",
            ),
            VisualAssetRef(
                provider=self.provider_name,
                query="phone screen recording horror closeup vertical",
                duration_seconds=10,
                license_note="Mock reference only; replace with licensed stock media.",
            ),
            VisualAssetRef(
                provider=self.provider_name,
                query="mirror shadow suspense cinematic vertical",
                duration_seconds=12,
                license_note="Mock reference only; replace with licensed stock media.",
            ),
        ]


class MockVoiceGenerator(VoiceGenerator):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, script: ScriptResult) -> VoiceoverMetadata:
        return VoiceoverMetadata(
            provider=self.settings.tts_provider,
            voice_name=self.settings.tts_voice_id,
            language_code="hi-IN",
            estimated_duration_seconds=script.estimated_duration_seconds,
            audio_path=None,
            is_mock=True,
        )


class MockVideoRenderer(VideoRenderer):
    def __init__(self, settings: Settings):
        self.settings = settings

    def render(
        self,
        script: ScriptResult,
        visuals: Sequence[VisualAssetRef],
        voiceover: VoiceoverMetadata,
    ) -> RenderMetadata:
        output_name = f"mock-{script.category}-{uuid4().hex[:8]}.mp4"
        return RenderMetadata(
            renderer=f"mock-renderer-planned-ffmpeg:{self.settings.ffmpeg_binary}",
            output_path=str(Path(self.settings.output_dir) / output_name),
            duration_seconds=script.estimated_duration_seconds,
            is_mock=True,
        )


class MockThumbnailGenerator(ThumbnailGenerator):
    def generate(self, script: ScriptResult) -> ThumbnailMetadata:
        return ThumbnailMetadata(
            provider="mock-thumbnail",
            title=f"{script.title} | RaatVerse",
            image_path=None,
            is_mock=True,
        )


class MockYouTubeUploader(YouTubeUploader):
    def __init__(self, settings: Settings):
        self.settings = settings

    def prepare_upload(
        self,
        script: ScriptResult,
        render: RenderMetadata,
        thumbnail: ThumbnailMetadata,
    ) -> UploadMetadata:
        description = (
            f"{script.hook}\n\n"
            f"Channel: {self.settings.channel_name} {self.settings.youtube_channel_handle}\n"
            "Phase 1 mock upload metadata only. Real uploads require OAuth setup and human approval."
        )
        return UploadMetadata(
            provider="mock-youtube",
            privacy_status=self.settings.upload_privacy_status,
            title=script.title,
            description=description,
            tags=["RaatVerse", "Hindi Horror", "Hinglish Story", "YouTube Shorts"],
            scheduled_for=None,
            youtube_video_id=f"mock-{uuid4().hex[:12]}",
            approval_required=self.settings.human_approval_required,
            is_mock=True,
        )


class MockAnalyticsFetcher(AnalyticsFetcher):
    def fetch_latest(self, youtube_video_id: str) -> AnalyticsSnapshotResult:
        return AnalyticsSnapshotResult(
            provider="mock-youtube-analytics",
            video_id=youtube_video_id,
            views=0,
            likes=0,
            comments=0,
            average_view_duration_seconds=0.0,
            is_mock=True,
        )
