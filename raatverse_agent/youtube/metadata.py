from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from raatverse_agent.assets.models import AssetPlan
from raatverse_agent.config import Settings
from raatverse_agent.rendering.models import VideoRender
from raatverse_agent.script_generation.models import ScriptDraft
from raatverse_agent.youtube.models import YouTubeMetadata


def generate_youtube_metadata(
    *,
    settings: Settings,
    draft: ScriptDraft,
    render: VideoRender,
    asset_plan: AssetPlan,
) -> YouTubeMetadata:
    title = _clean_title(draft.title)
    tags = _tags_for_draft(draft)
    description = _description(settings, draft, asset_plan)
    return YouTubeMetadata(
        title=title,
        description=description,
        tags=tags,
        category_id=settings.youtube_category_id,
        privacy_status="private",
        scheduled_publish_at=None,
        contains_synthetic_media=settings.youtube_contains_synthetic_media,
        self_declared_made_for_kids=settings.youtube_self_declared_made_for_kids,
        default_language=settings.youtube_default_language,
    )


def next_default_publish_time(settings: Settings, *, now: datetime | None = None) -> datetime:
    timezone_name = "Asia/Kolkata" if settings.default_timezone == "Asia/Calcutta" else settings.default_timezone
    tz = ZoneInfo(timezone_name)
    current = now.astimezone(tz) if now else datetime.now(tz)
    hour, minute = [int(part) for part in settings.youtube_default_schedule_time.split(":", 1)]
    candidate = datetime.combine(current.date(), time(hour=hour, minute=minute), tzinfo=tz)
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate


def parse_publish_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Scheduled publish time must include a timezone offset.")
    return parsed


def _clean_title(title: str) -> str:
    cleaned = " ".join(title.split())
    if len(cleaned) <= 96:
        return cleaned
    return cleaned[:93].rstrip() + "..."


def _tags_for_draft(draft: ScriptDraft) -> list[str]:
    base = [
        "RaatVerse",
        "Hindi horror story",
        "mystery shorts",
        "suspense story",
        "Hindi stories",
        "Shorts",
        draft.category.replace("_", " "),
        draft.story_type.replace("_", " "),
    ]
    seen: set[str] = set()
    tags: list[str] = []
    for tag in base:
        normalized = tag.lower()
        if normalized not in seen:
            seen.add(normalized)
            tags.append(tag)
    return tags


def _description(settings: Settings, draft: ScriptDraft, asset_plan: AssetPlan) -> str:
    summary = draft.hook
    hashtags = "#RaatVerse #HindiHorror #MysteryShorts #Suspense #Shorts"
    attribution = _attribution_notes(asset_plan)
    parts = [
        summary,
        "",
        settings.outro_cta,
        "",
        hashtags,
    ]
    if attribution:
        parts.extend(["", "Media/source notes:", *attribution])
    parts.extend(
        [
            "",
            "This RaatVerse Short is a fictional cinematic Hindi/Hinglish story.",
        ]
    )
    return "\n".join(parts)


def _attribution_notes(asset_plan: AssetPlan) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for item in asset_plan.media_assets:
        if item.provider == "mock":
            continue
        creator = item.creator_name or "Unknown creator"
        source = item.source_url
        note = f"- {item.provider}: {creator} | {source}"
        if item.license_note:
            note += f" | {item.license_note}"
        if note not in seen:
            seen.add(note)
            notes.append(note)
    return notes[:12]
