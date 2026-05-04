from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScriptDraftStatus = Literal["draft", "approved", "rejected", "needs_revision"]


class ScriptSceneBeat(BaseModel):
    start_second: int = Field(ge=0)
    end_second: int = Field(ge=0)
    narration: str = Field(min_length=1)
    visual_suggestion: str = Field(min_length=1)
    narration_segment: str | None = None
    stock_search_query: str | None = None
    negative_keywords: list[str] = Field(default_factory=list)
    mood: str | None = None
    location: str | None = None
    camera_motion: str | None = None

    @field_validator("end_second")
    @classmethod
    def end_must_be_after_start(cls, value: int, info) -> int:
        start = info.data.get("start_second")
        if start is not None and value <= start:
            raise ValueError("end_second must be greater than start_second")
        return value


class ScriptValidationResult(BaseModel):
    is_valid: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def ok(cls, warnings: list[str] | None = None) -> "ScriptValidationResult":
        return cls(is_valid=True, warnings=warnings or [])

    @classmethod
    def failed(
        cls,
        issues: list[str],
        warnings: list[str] | None = None,
    ) -> "ScriptValidationResult":
        return cls(is_valid=False, issues=issues, warnings=warnings or [])

    def merge(self, other: "ScriptValidationResult") -> "ScriptValidationResult":
        return ScriptValidationResult(
            is_valid=self.is_valid and other.is_valid,
            issues=[*self.issues, *other.issues],
            warnings=[*self.warnings, *other.warnings],
        )


class ScriptDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    draft_uid: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    story_type: str = Field(min_length=1, max_length=80)
    hook: str = Field(min_length=1, max_length=300)
    narration_script: str = Field(min_length=1, alias="full_narration_script")
    tts_narration_script: str | None = Field(
        default=None,
        alias="narration_hindi_devanagari_for_tts",
    )
    scene_beats: list[ScriptSceneBeat] = Field(default_factory=list)
    subtitle_lines: list[str] = Field(default_factory=list)
    cta_line: str = Field(min_length=1)
    estimated_duration_seconds: int = Field(ge=1)
    language_style: str = Field(min_length=1)
    safety_notes: list[str] = Field(default_factory=list)
    originality_notes: list[str] = Field(default_factory=list)
    status: ScriptDraftStatus = "draft"
    rejection_reason: str | None = None
    provider: str = "mock"
    prompt_version: str = "raatverse-script-v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScriptGenerationRequest(BaseModel):
    category: str | None = None
    story_type: str | None = None
    seed: str | None = None
    language_style: str | None = None
    target_duration_seconds: int | None = None
    mock: bool = False
    auto_category: bool = False
    category_preferences: list[str] = Field(default_factory=list)


class ScriptGenerationResponse(BaseModel):
    draft: ScriptDraft | None = None
    validation: ScriptValidationResult
    provider: str
    saved_draft_id: int | None = None
    raw_response: str | None = None
    error: str | None = None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip("- ").strip() for line in value.splitlines() if line.strip()]
    return [str(value).strip()]


def _coerce_scene_beat(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        start = item.get("start_second", item.get("start", index * 10))
        end = item.get("end_second", item.get("end", (index + 1) * 10))
        return {
            "start_second": int(start),
            "end_second": int(end),
            "narration": str(item.get("narration", item.get("line", ""))).strip(),
            "visual_suggestion": str(
                item.get("visual_suggestion", item.get("visual", item.get("scene", "")))
            ).strip(),
            "narration_segment": str(
                item.get("narration_segment", item.get("narration", item.get("line", "")))
            ).strip()
            or None,
            "stock_search_query": str(
                item.get("stock_search_query", item.get("search_query", ""))
            ).strip()
            or None,
            "negative_keywords": _as_list(item.get("negative_keywords")),
            "mood": str(item.get("mood", "")).strip() or None,
            "location": str(item.get("location", "")).strip() or None,
            "camera_motion": str(item.get("camera_motion", "")).strip() or None,
        }
    return {
        "start_second": index * 10,
        "end_second": (index + 1) * 10,
        "narration": str(item).strip(),
        "visual_suggestion": str(item).strip(),
    }


def script_draft_from_payload(
    payload: dict[str, Any],
    *,
    provider: str,
    prompt_version: str,
    default_category: str,
    default_story_type: str,
    default_language_style: str,
    cta_line: str,
) -> ScriptDraft:
    raw_scene_beats = payload.get("scene_beats") or payload.get("sceneBeats") or []
    scene_beats = [
        _coerce_scene_beat(item, index)
        for index, item in enumerate(raw_scene_beats)
    ]

    narration_script = (
        payload.get("narration_script")
        or payload.get("full_narration_script")
        or payload.get("narration_hinglish")
        or payload.get("script")
        or payload.get("full_script")
        or ""
    )
    tts_narration_script = (
        payload.get("narration_hindi_devanagari_for_tts")
        or payload.get("tts_narration_script")
        or payload.get("tts_text")
    )

    return ScriptDraft(
        title=str(payload.get("title", "")).strip(),
        category=str(payload.get("category", default_category)).strip() or default_category,
        story_type=str(payload.get("story_type", default_story_type)).strip() or default_story_type,
        hook=str(payload.get("hook", "")).strip(),
        full_narration_script=str(narration_script).strip(),
        narration_hindi_devanagari_for_tts=(
            str(tts_narration_script).strip() if tts_narration_script else None
        ),
        scene_beats=scene_beats,
        subtitle_lines=_as_list(payload.get("subtitle_lines") or payload.get("subtitles")),
        cta_line=str(payload.get("cta_line", cta_line)).strip() or cta_line,
        estimated_duration_seconds=int(
            payload.get("estimated_duration_seconds")
            or payload.get("duration_seconds")
            or 0
        ),
        language_style=str(
            payload.get("language_style", default_language_style)
        ).strip() or default_language_style,
        safety_notes=_as_list(payload.get("safety_notes")),
        originality_notes=_as_list(payload.get("originality_notes")),
        provider=provider,
        prompt_version=prompt_version,
    )
