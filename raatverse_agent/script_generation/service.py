from __future__ import annotations

from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.script_generation.models import (
    ScriptDraft,
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    ScriptValidationResult,
)
from raatverse_agent.script_generation.prompts import (
    get_prompt_template,
    normalize_category,
)
from raatverse_agent.script_generation.strategy import ScriptCategoryStrategy
from raatverse_agent.script_generation.uniqueness import UniquenessChecker
from raatverse_agent.script_generation.validation import validate_script_draft
from raatverse_agent.services.gemini import GeminiScriptGenerator
from raatverse_agent.services.interfaces import ScriptDraftGenerator
from raatverse_agent.services.mock import MockDraftScriptGenerator


def create_script_draft_generator(settings: Settings, *, mock: bool = False) -> ScriptDraftGenerator:
    provider = settings.llm_provider.strip().lower()
    if mock or provider == "mock":
        return MockDraftScriptGenerator(settings)
    if provider in {"gemini", "gemini-compatible", "google-gemini"}:
        return GeminiScriptGenerator(settings)
    raise ValueError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Supported: mock, gemini, gemini-compatible."
    )


class ScriptDraftService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RaatVerseRepository,
        generator: ScriptDraftGenerator,
    ):
        self.settings = settings
        self.repository = repository
        self.generator = generator
        self.strategy = ScriptCategoryStrategy(settings)
        self.uniqueness = UniquenessChecker(settings)

    def generate(self, request: ScriptGenerationRequest) -> ScriptGenerationResponse:
        prepared = self._prepare_request(request)
        latest_response: ScriptGenerationResponse | None = None

        for attempt in range(self.settings.script_generation_max_attempts):
            attempt_request = prepared
            if attempt > 0:
                retry_seed = (
                    f"{prepared.seed or 'fresh premise'} | Retry {attempt + 1}: "
                    "avoid the validation and originality issues from the previous attempt."
                )
                attempt_request = prepared.model_copy(update={"seed": retry_seed})

            response = self.generator.generate_draft(attempt_request)
            latest_response = response
            if response.draft is None:
                return response

            validation = self._validate(response.draft)
            if validation.is_valid or attempt == self.settings.script_generation_max_attempts - 1:
                status = "draft" if validation.is_valid else "needs_revision"
                saved = self._save(response.draft, validation, response.raw_response, status=status)
                return ScriptGenerationResponse(
                    draft=saved,
                    validation=validation,
                    provider=response.provider,
                    saved_draft_id=saved.id,
                    raw_response=response.raw_response,
                    error=None if validation.is_valid else "Draft saved with validation issues.",
                )

        return latest_response or ScriptGenerationResponse(
            draft=None,
            validation=ScriptValidationResult.failed(["Script generation did not return a response."]),
            provider="unknown",
            error="Script generation did not return a response.",
        )

    def regenerate_rejected(self, draft_id: int) -> ScriptGenerationResponse:
        rejected = self.repository.get_script_draft(draft_id)
        if rejected is None:
            return ScriptGenerationResponse(
                draft=None,
                validation=ScriptValidationResult.failed([f"Script draft {draft_id} was not found."]),
                provider="unknown",
                error=f"Script draft {draft_id} was not found.",
            )
        if rejected.status != "rejected":
            return ScriptGenerationResponse(
                draft=None,
                validation=ScriptValidationResult.failed(
                    [f"Script draft {draft_id} must be rejected before regeneration."]
                ),
                provider="unknown",
                error=f"Script draft {draft_id} must be rejected before regeneration.",
            )

        seed = (
            "Regenerate this rejected RaatVerse draft as a fresh original story. "
            f"Old title: {rejected.title}. Old hook: {rejected.hook}. "
            f"Rejection reason: {rejected.rejection_reason or 'No reason provided'}. "
            "Keep category and story type, but create a different premise, hook, title, and twist."
        )
        return self.generate(
            ScriptGenerationRequest(
                category=rejected.category,
                story_type=rejected.story_type,
                seed=seed,
                mock=True if rejected.provider == "mock" else False,
            )
        )

    def _prepare_request(self, request: ScriptGenerationRequest) -> ScriptGenerationRequest:
        self.repository.init_category_scores(self.settings.all_categories)
        category_scores = self.repository.get_category_score_states()
        ranked = self.strategy.ranked_categories(self.settings.script_categories, category_scores)

        category = normalize_category(request.category or self.strategy.choose_category(
            self.settings.script_categories,
            category_scores,
        ))
        template = get_prompt_template(category)
        return request.model_copy(
            update={
                "category": category,
                "story_type": request.story_type or template["story_type"],
                "language_style": request.language_style or self.settings.language_style,
                "target_duration_seconds": request.target_duration_seconds
                or self.settings.target_duration_seconds,
                "category_preferences": ranked,
            }
        )

    def _validate(self, draft: ScriptDraft) -> ScriptValidationResult:
        structural = validate_script_draft(self.settings, draft)
        recent = self.repository.get_recent_script_context(limit=self.settings.script_recent_window)
        uniqueness = self.uniqueness.evaluate(draft, recent)
        return structural.merge(uniqueness)

    def _save(
        self,
        draft: ScriptDraft,
        validation: ScriptValidationResult,
        raw_response: str | None,
        *,
        status: str,
    ) -> ScriptDraft:
        draft.status = status  # type: ignore[assignment]
        record = self.repository.create_script_draft(
            draft=draft,
            validation=validation,
            raw_response=raw_response,
        )
        saved = self.repository.get_script_draft(record.id)
        if saved is None:
            raise RuntimeError("Saved script draft could not be loaded.")
        return saved
