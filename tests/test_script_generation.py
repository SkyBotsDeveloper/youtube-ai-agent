import pytest

from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.script_generation.models import (
    ScriptDraft,
    ScriptGenerationRequest,
    ScriptSceneBeat,
    ScriptValidationResult,
)
from raatverse_agent.script_generation.parsing import extract_json_object
from raatverse_agent.script_generation.prompts import build_script_prompt
from raatverse_agent.script_generation.service import ScriptDraftService
from raatverse_agent.script_generation.uniqueness import UniquenessChecker
from raatverse_agent.script_generation.validation import validate_script_draft
from raatverse_agent.services.gemini import GeminiScriptGenerator, LLMConfigurationError
from raatverse_agent.services.mock import MockDraftScriptGenerator


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'scripts.db').as_posix()}",
        "script_categories_csv": "horror,mystery,suspense,emotional_twist,thriller,urban_legend,psychological",
        "story_categories_csv": "horror,mystery",
        "llm_api_key": "",
    }
    values.update(overrides)
    return Settings(**values)


def _valid_draft(settings: Settings) -> ScriptDraft:
    hook = "Raat ke 2:17 baje, Meera ke phone par uski hi awaaz ka message aaya."
    narration = (
        f"{hook} "
        "Message mein sirf teen shabd the: darwaza mat khol. Meera ne corridor dekha, "
        "to geeli mitti ke nishaan seedhe uske kamre tak aa rahe the. Usne socha koi prank hai, "
        "par phone ki recording mein kal wali Meera ro rahi thi. Woh keh rahi thi ki jo aadmi bahar khada hai, "
        "woh aadmi nahi, uski bhooli hui yaad hai. Mirror mein Meera ne apne haath mein ek chabi dekhi, "
        "jabki asli haath khaali tha. Subah uske phone mein ek aur message tha: aaj raat sach yaad aa jayega. "
        f"{settings.outro_cta}"
    )
    return ScriptDraft(
        title="Horror: Aakhri Message",
        category="horror",
        story_type="atmospheric_horror",
        hook=hook,
        full_narration_script=narration,
        scene_beats=[
            ScriptSceneBeat(
                start_second=0,
                end_second=3,
                narration=hook,
                visual_suggestion="Phone glowing in a dark room.",
            )
        ],
        subtitle_lines=["Raat ke 2:17 baje phone baja."],
        cta_line=settings.outro_cta,
        estimated_duration_seconds=settings.target_duration_seconds,
        language_style=settings.language_style,
        safety_notes=["No gore-heavy content."],
        originality_notes=["Original mirror-message setup."],
        provider="mock",
    )


def test_prompt_template_creation(tmp_path):
    settings = _settings(tmp_path)
    prompt = build_script_prompt(settings, ScriptGenerationRequest(category="urban-legend"))

    assert "urban_legend" in prompt
    assert settings.outro_cta in prompt
    assert "Return only a valid JSON object" in prompt


def test_json_recovery_from_fenced_llm_response():
    parsed = extract_json_object(
        '```json\n{"title": "Test", "scene_beats": [{"start_second": 0, "end_second": 3}]}\n```'
    )

    assert parsed["title"] == "Test"
    assert parsed["scene_beats"][0]["end_second"] == 3


def test_mock_script_generation_saves_draft(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=MockDraftScriptGenerator(settings),
        )
        response = service.generate(ScriptGenerationRequest(category="horror", mock=True))
        drafts = repository.list_script_drafts()

    assert response.draft is not None
    assert response.saved_draft_id is not None
    assert response.validation.is_valid is True
    assert len(drafts) == 1
    assert drafts[0].status == "draft"


def test_script_validation_blocks_missing_cta(tmp_path):
    settings = _settings(tmp_path)
    draft = _valid_draft(settings)
    draft.narration_script = draft.narration_script.replace(settings.outro_cta, "")

    result = validate_script_draft(settings, draft)

    assert result.is_valid is False
    assert any("CTA" in issue for issue in result.issues)


def test_uniqueness_check_flags_repetitive_title_hook_and_script(tmp_path):
    settings = _settings(tmp_path)
    draft = _valid_draft(settings)
    existing = [
        {
            "title": draft.title,
            "hook": draft.hook,
            "category": draft.category,
            "story_type": draft.story_type,
            "narration_script": draft.narration_script,
        }
    ]

    result = UniquenessChecker(settings).evaluate(draft, existing)

    assert result.is_valid is False
    assert any("Title is too similar" in issue for issue in result.issues)
    assert any("Hook is too similar" in issue for issue in result.issues)


def test_draft_save_show_approve_reject_workflow(tmp_path):
    settings = _settings(tmp_path)
    draft = _valid_draft(settings)
    validation = ScriptValidationResult.ok()
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        record = repository.create_script_draft(draft=draft, validation=validation)
        listed = repository.list_script_drafts()
        shown = repository.get_script_draft(record.id)
        approved = repository.update_script_draft_status(record.id, "approved")
        rejected = repository.update_script_draft_status(record.id, "rejected", "Needs a stronger twist.")

    assert len(listed) == 1
    assert shown is not None
    assert shown.id == record.id
    assert approved is not None
    assert approved.status == "approved"
    assert rejected is not None
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "Needs a stronger twist."


def test_no_llm_api_key_is_allowed_in_config_but_real_provider_errors(tmp_path):
    settings = _settings(tmp_path, llm_provider="gemini", llm_model="gemini-test")

    assert settings.llm_api_key == ""
    with pytest.raises(LLMConfigurationError):
        GeminiScriptGenerator(settings).generate_draft(ScriptGenerationRequest(category="horror"))
