from __future__ import annotations

from textwrap import dedent

from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptGenerationRequest

PROMPT_VERSION = "raatverse-script-v2"

PROMPT_TEMPLATES: dict[str, dict[str, str]] = {
    "horror": {
        "story_type": "atmospheric_horror",
        "tone": "dark, cinematic, eerie, suspense-first, no gore",
        "premise": "A normal night turns unsettling through sound, shadow, memory, or a place that feels alive.",
    },
    "mystery": {
        "story_type": "short_mystery",
        "tone": "curious, clue-driven, tense, premium",
        "premise": "A small impossible clue reveals a hidden truth in the final reveal.",
    },
    "suspense": {
        "story_type": "slow_burn_suspense",
        "tone": "quiet tension, cinematic pauses, escalating dread",
        "premise": "The narrator notices one wrong detail, then each second makes it harder to ignore.",
    },
    "emotional_twist": {
        "story_type": "emotional_twist",
        "tone": "haunting, emotional, restrained, bittersweet",
        "premise": "A frightening setup resolves into an emotional reveal without becoming sentimental.",
    },
    "thriller": {
        "story_type": "micro_thriller",
        "tone": "urgent, tense, grounded, cinematic",
        "premise": "A late-night decision forces the protagonist to decode danger quickly.",
    },
    "urban_legend": {
        "story_type": "fictional_urban_legend",
        "tone": "folklore-like, mysterious, modern Indian setting",
        "premise": "A fictional local rumor becomes personally relevant to the protagonist.",
    },
    "psychological": {
        "story_type": "psychological_suspense",
        "tone": "internal tension, unreliable perception, safe and non-graphic",
        "premise": "The fear comes from memory, guilt, or perception rather than explicit violence.",
    },
}


def normalize_category(category: str) -> str:
    return category.strip().lower().replace("-", "_").replace(" ", "_")


def supported_prompt_categories() -> tuple[str, ...]:
    return tuple(PROMPT_TEMPLATES.keys())


def get_prompt_template(category: str) -> dict[str, str]:
    normalized = normalize_category(category)
    if normalized not in PROMPT_TEMPLATES:
        supported = ", ".join(supported_prompt_categories())
        raise ValueError(f"Unsupported script category '{category}'. Supported: {supported}")
    return PROMPT_TEMPLATES[normalized]


def build_script_prompt(settings: Settings, request: ScriptGenerationRequest) -> str:
    category = normalize_category(request.category or "horror")
    template = get_prompt_template(category)
    story_type = request.story_type or template["story_type"]
    language_style = request.language_style or settings.language_style
    duration = request.target_duration_seconds or settings.target_duration_seconds
    preferences = ", ".join(request.category_preferences) or "balanced variety"
    seed = request.seed or "create a fresh original premise"

    return dedent(
        f"""
        You are the story writer for the YouTube Shorts channel RaatVerse (@RaatVerseHindi).
        Create one original Hindi/Hinglish short narration script for human review.

        Channel niche:
        - Hindi/Hinglish horror, mystery, suspense, thriller, urban legend, psychological, and emotional twist stories.
        - Style: dark, cinematic, mysterious, premium.
        - Audience: general teen/adult Shorts viewers.

        Category: {category}
        Story type: {story_type}
        Category strategy preferences: {preferences}
        Language style: {language_style}
        Target duration: {duration} seconds. Hard bounds: {settings.min_video_seconds}-{settings.max_video_seconds} seconds.
        Seed or constraint: {seed}

        Category template:
        - Tone: {template["tone"]}
        - Premise direction: {template["premise"]}

        Required timing structure:
        - 0-3 sec: strong hook.
        - 3-45 sec: build-up with cinematic suspense.
        - 45-65 sec: twist or reveal.
        - Last 5-10 sec: CTA exactly as supplied.
        - Keep subtitle lines short enough for bold Shorts captions.
        - Write the display narration in natural Hinglish, but also provide a Devanagari Hindi narration variant for TTS.
        - Use scene-specific visual search keywords. Avoid generic one-word visual terms.

        Safety and originality boundaries:
        - Must be original.
        - No gore-heavy content.
        - No explicit sexual content.
        - No hate, slurs, or demeaning protected groups.
        - No real-person fake allegations.
        - No copied movie, anime, game, or celebrity characters.
        - No misleading true-story claim. If it feels like a legend, keep it clearly fictional.
        - No graphic harm involving children.
        - Avoid repetitive templates, generic haunted-house cliches, and overused endings.

        CTA line, must appear exactly once at the end:
        {settings.outro_cta}

        Return only a valid JSON object. Do not wrap it in markdown.
        Required JSON keys:
        {{
          "title": "short title under 80 characters",
          "category": "{category}",
          "story_type": "{story_type}",
          "hook": "0-3 sec opening line",
          "narration_hinglish": "full Hinglish display narration including the CTA at the end",
          "narration_hindi_devanagari_for_tts": "same complete narration in natural Devanagari Hindi for hi-IN TTS voices",
          "narration_script": "same as narration_hinglish, included for compatibility",
          "scene_beats": [
            {{
              "start_second": 0,
              "end_second": 3,
              "narration": "short Hinglish line or beat",
              "narration_segment": "matching narration segment for this beat",
              "visual_suggestion": "specific vertical cinematic visual suggestion",
              "stock_search_query": "specific stock search query such as dark abandoned house interior night vertical",
              "negative_keywords": ["generic", "cartoon", "bright daylight"],
              "mood": "eerie, lonely, tense, emotional, or reveal",
              "location": "specific place or texture visible in the scene",
              "camera_motion": "slow push-in, handheld drift, static close-up, or slow pan"
            }}
          ],
          "subtitle_lines": ["short subtitle-friendly line"],
          "cta_line": "{settings.outro_cta}",
          "estimated_duration_seconds": {duration},
          "language_style": "{language_style}",
          "safety_notes": ["brief note confirming boundaries"],
          "originality_notes": ["brief note on what makes this premise distinct"]
        }}
        """
    ).strip()
