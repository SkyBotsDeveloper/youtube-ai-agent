from __future__ import annotations

import httpx

from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import (
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    ScriptValidationResult,
    script_draft_from_payload,
)
from raatverse_agent.script_generation.parsing import ScriptParseError, extract_json_object
from raatverse_agent.script_generation.prompts import (
    PROMPT_VERSION,
    build_script_prompt,
    get_prompt_template,
    normalize_category,
)
from raatverse_agent.services.interfaces import ScriptDraftGenerator

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class LLMConfigurationError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    pass


class GeminiScriptGenerator(ScriptDraftGenerator):
    """Gemini-compatible REST script generator using generateContent."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _endpoint(self) -> str:
        base_url = (self.settings.llm_base_url or DEFAULT_GEMINI_BASE_URL).rstrip("/")
        model = self.settings.llm_model.strip()
        if not model:
            raise LLMConfigurationError("LLM_MODEL is required for real script generation.")
        model_resource = model if model.startswith("models/") else f"models/{model}"
        return f"{base_url}/{model_resource}:generateContent"

    def generate_draft(self, request: ScriptGenerationRequest) -> ScriptGenerationResponse:
        if not self.settings.llm_api_key:
            raise LLMConfigurationError(
                "LLM_API_KEY is not configured. Use --mock for local dry runs or set a Gemini-compatible API key."
            )

        category = normalize_category(request.category or self.settings.script_categories[0])
        template = get_prompt_template(category)
        story_type = request.story_type or template["story_type"]
        prompt_request = request.model_copy(
            update={
                "category": category,
                "story_type": story_type,
                "language_style": request.language_style or self.settings.language_style,
                "target_duration_seconds": request.target_duration_seconds
                or self.settings.target_duration_seconds,
            }
        )
        prompt = build_script_prompt(self.settings, prompt_request)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": self.settings.llm_temperature,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                response = client.post(
                    self._endpoint(),
                    headers={
                        "x-goog-api-key": self.settings.llm_api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise LLMProviderError(
                f"Gemini-compatible provider returned HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Gemini-compatible provider request failed: {exc}") from exc

        response_json = response.json()
        raw_text = self._extract_text(response_json)
        try:
            parsed = extract_json_object(raw_text)
            draft = script_draft_from_payload(
                parsed,
                provider=self.settings.llm_provider,
                prompt_version=PROMPT_VERSION,
                default_category=category,
                default_story_type=story_type,
                default_language_style=prompt_request.language_style or self.settings.language_style,
                cta_line=self.settings.outro_cta,
            )
        except (ScriptParseError, ValueError) as exc:
            return ScriptGenerationResponse(
                draft=None,
                validation=ScriptValidationResult.failed([str(exc)]),
                provider=self.settings.llm_provider,
                raw_response=raw_text,
                error=str(exc),
            )

        return ScriptGenerationResponse(
            draft=draft,
            validation=ScriptValidationResult.ok(),
            provider=self.settings.llm_provider,
            raw_response=raw_text,
        )

    @staticmethod
    def _extract_text(response_json: dict) -> str:
        candidates = response_json.get("candidates") or []
        if not candidates:
            raise LLMProviderError("Gemini-compatible provider returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts") or []
        texts = [str(part.get("text", "")) for part in parts if part.get("text")]
        if not texts:
            raise LLMProviderError("Gemini-compatible provider returned no text parts.")
        return "\n".join(texts)
