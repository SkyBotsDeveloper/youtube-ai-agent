from __future__ import annotations

import re
from dataclasses import dataclass

from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
SUBSCRIBE_DEVANAGARI = "\u0938\u092c\u094d\u0938\u0915\u094d\u0930\u093e\u0907\u092c"
SUBSCRIBE_KAREN_DEVANAGARI = f"{SUBSCRIBE_DEVANAGARI} \u0915\u0930\u0947\u0902"
DEFAULT_CTA_TTS_TEXT = (
    "\u0905\u0917\u0930 \u0915\u0939\u093e\u0928\u0940 \u092a\u0938\u0902\u0926 "
    "\u0906\u0908 \u0939\u094b, \u0924\u094b \u0930\u093e\u0924\u0935\u0930\u094d\u0938 "
    f"\u091a\u0948\u0928\u0932 \u0915\u094b {SUBSCRIBE_KAREN_DEVANAGARI}\u0964 "
    "\u0915\u0932 \u0930\u093e\u0924 \u090f\u0915 \u0914\u0930 \u0928\u0908 "
    "\u0915\u0939\u093e\u0928\u0940 \u092e\u093f\u0932\u0947\u0917\u0940\u0964"
)

HINGLISH_WORD_MAP: dict[str, str] = {
    "aaj": "आज",
    "aayi": "आई",
    "aayega": "आएगा",
    "aayegi": "आएगी",
    "aaungi": "आऊंगी",
    "agar": "अगर",
    "akela": "अकेला",
    "andar": "अंदर",
    "apne": "अपने",
    "aur": "और",
    "awaaz": "आवाज",
    "bacha": "बचा",
    "baje": "बजे",
    "baar": "बार",
    "bahar": "बाहर",
    "chabi": "चाबी",
    "darwaza": "दरवाजा",
    "deewaar": "दीवार",
    "diwar": "दीवार",
    "geeli": "गीली",
    "gehri": "गहरी",
    "ghar": "घर",
    "hai": "है",
    "har": "हर",
    "hi": "ही",
    "ho": "हो",
    "hoga": "होगा",
    "hoon": "हूं",
    "is": "इस",
    "iss": "इस",
    "jab": "जब",
    "jahan": "जहां",
    "kahani": "कहानी",
    "kal": "कल",
    "kamra": "कमरा",
    "kamre": "कमरे",
    "karo": "करो",
    "ke": "के",
    "khaali": "खाली",
    "ki": "की",
    "kisi": "किसी",
    "koi": "कोई",
    "main": "मैं",
    "maine": "मैंने",
    "mat": "मत",
    "mein": "में",
    "mera": "मेरा",
    "meera": "मीरा",
    "message": "मैसेज",
    "milega": "मिलेगा",
    "milegi": "मिलेगी",
    "mitti": "मिट्टी",
    "nahi": "नहीं",
    "nayi": "नई",
    "nishaan": "निशान",
    "par": "पर",
    "pasand": "पसंद",
    "phone": "फोन",
    "purane": "पुराने",
    "raat": "रात",
    "raatverse": "रातवर्स",
    "recording": "रिकॉर्डिंग",
    "screen": "स्क्रीन",
    "sirf": "सिर्फ",
    "subscribe": "सब्सक्राइब",
    "tha": "था",
    "thi": "थी",
    "to": "तो",
    "tu": "तू",
    "tum": "तुम",
    "uske": "उसके",
    "uski": "उसकी",
    "wali": "वाली",
    "wapas": "वापस",
    "woh": "वह",
    "yeh": "यह",
}


@dataclass(frozen=True)
class PreparedTTSText:
    display_text: str
    tts_text: str
    chunks: list[str]
    original_characters: int
    input_characters: int
    warnings: list[str]
    cta_tts_text: str = ""
    cta_tts_mode: str = "none"
    cta_slowing_enabled: bool = False
    cta_rate_reduction: int = 0


def prepare_tts_text(draft: ScriptDraft, settings: Settings) -> PreparedTTSText:
    display_text = draft.narration_script.strip()
    source = _select_tts_source(draft, settings)
    source, cta_tts_text, cta_tts_mode = apply_cta_tts_normalization(source, draft, settings)
    normalized = normalize_tts_text(source, settings)
    normalized_cta = normalize_tts_text(cta_tts_text, settings) if cta_tts_text else ""
    chunks = chunk_tts_text_preserving_cta(
        normalized,
        settings.tts_max_chars_per_chunk,
        cta_text=normalized_cta,
    )
    warnings = _validate_tts_text(display_text, normalized)
    return PreparedTTSText(
        display_text=display_text,
        tts_text=normalized,
        chunks=chunks,
        original_characters=len(display_text),
        input_characters=len(normalized),
        warnings=warnings,
        cta_tts_text=normalized_cta,
        cta_tts_mode=cta_tts_mode,
        cta_slowing_enabled=settings.tts_cta_slower,
        cta_rate_reduction=settings.tts_cta_rate_reduction,
    )


def normalize_tts_text(text: str, settings: Settings) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    if settings.tts_pause_style == "punctuation":
        pause = "। " if DEVANAGARI_RE.search(cleaned) else ". "
        cleaned = re.sub(r"(\.\s*){2,}|…+", pause, cleaned)
        cleaned = re.sub(r"\s*[-–—]\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?।])", r"\1", cleaned)
    cleaned = re.sub(r"([,.;:!?।])([^\s\"'])", r"\1 \2", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned)
    return cleaned.strip()


def chunk_tts_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []

    sentence_parts = [
        part.strip()
        for part in re.split(r"(?<=[.!?।])\s+", text)
        if part.strip()
    ]
    chunks: list[str] = []
    current = ""
    for part in sentence_parts:
        if len(part) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_part(part, max_chars))
            continue
        candidate = f"{current} {part}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = part
    if current:
        chunks.append(current.strip())
    return chunks


def chunk_tts_text_preserving_cta(text: str, max_chars: int, *, cta_text: str = "") -> list[str]:
    text = text.strip()
    cta_text = cta_text.strip()
    if not text:
        return []
    if not cta_text:
        return chunk_tts_text(text, max_chars)

    cta_start = text.rfind(cta_text)
    if cta_start < 0:
        return chunk_tts_text(text, max_chars)

    story_text = text[:cta_start].strip()
    cta_tail = text[cta_start:].strip()
    chunks = chunk_tts_text(story_text, max_chars) if story_text else []
    chunks.extend(chunk_tts_text(cta_tail, max_chars))
    return chunks


def build_tts_quality_metadata(
    prepared: PreparedTTSText,
    *,
    audio_duration_seconds: float | None,
    estimated_script_duration_seconds: float | None,
) -> dict:
    warnings = list(prepared.warnings)
    duration_delta_ratio = None
    if audio_duration_seconds and estimated_script_duration_seconds:
        duration_delta_ratio = abs(audio_duration_seconds - estimated_script_duration_seconds) / max(
            1.0,
            estimated_script_duration_seconds,
        )
        if duration_delta_ratio > 0.15:
            warnings.append(
                "Audio duration differs from estimated script duration by more than 15%."
            )
    return {
        "input_characters": prepared.input_characters,
        "original_characters": prepared.original_characters,
        "chunk_count": len(prepared.chunks),
        "chunk_lengths": [len(chunk) for chunk in prepared.chunks],
        "audio_duration_seconds": audio_duration_seconds,
        "estimated_script_duration_seconds": estimated_script_duration_seconds,
        "duration_delta_ratio": duration_delta_ratio,
        "cta_tts_text": prepared.cta_tts_text,
        "cta_tts_mode": prepared.cta_tts_mode,
        "cta_tts_override_used": prepared.cta_tts_mode == "override",
        "cta_tts_auto_generated": prepared.cta_tts_mode == "auto",
        "tts_cta_slower": prepared.cta_slowing_enabled,
        "tts_cta_rate_reduction": prepared.cta_rate_reduction,
        "cta_chunk_count": sum(1 for chunk in prepared.chunks if is_cta_tts_chunk(chunk, prepared.cta_tts_text)),
        "warnings": warnings,
    }


def convert_hinglish_to_devanagari(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        replacement = HINGLISH_WORD_MAP.get(word.lower())
        return replacement if replacement else word

    converted = re.sub(r"[A-Za-z]+", replace, text)
    converted = converted.replace(".", "।")
    return converted


def build_cta_tts_text(settings: Settings) -> str:
    override = settings.cta_tts_override.strip()
    if override:
        return override
    return DEFAULT_CTA_TTS_TEXT


def apply_cta_tts_normalization(
    source: str,
    draft: ScriptDraft,
    settings: Settings,
) -> tuple[str, str, str]:
    cta_tts_text = build_cta_tts_text(settings)
    mode = "override" if settings.cta_tts_override.strip() else "auto"
    display_cta = (draft.cta_line or settings.outro_cta).strip()
    source = source.strip()
    if not source or not cta_tts_text:
        return source, "", "none"

    if display_cta and display_cta in source:
        return source.replace(display_cta, cta_tts_text), cta_tts_text, mode

    without_display_cta = _remove_common_display_cta(source, display_cta)
    if without_display_cta != source:
        return f"{without_display_cta.rstrip()} {cta_tts_text}".strip(), cta_tts_text, mode

    normalized_source = _normalize_for_match(source)
    if (
        ("raatverse ko subscribe karo" in normalized_source or "subscribe karo" in normalized_source)
        and "kal raat" in normalized_source
    ):
        return f"{source.rstrip()} {cta_tts_text}".strip(), cta_tts_text, mode

    if SUBSCRIBE_DEVANAGARI in source and SUBSCRIBE_KAREN_DEVANAGARI not in source:
        return _ensure_devanagari_subscribe_karen(source), cta_tts_text, mode

    return source, "", "none"


def is_cta_tts_chunk(text: str, cta_text: str | Settings = "") -> bool:
    if isinstance(cta_text, Settings):
        cta_text = build_cta_tts_text(cta_text)
    normalized = _normalize_for_match(text)
    normalized_cta = _normalize_for_match(str(cta_text or ""))
    if normalized_cta and (normalized_cta in normalized or normalized in normalized_cta):
        return True
    return "subscribe" in normalized or SUBSCRIBE_DEVANAGARI in text


def _remove_common_display_cta(source: str, display_cta: str) -> str:
    cleaned = source.replace(display_cta, "") if display_cta else source
    patterns = [
        r"agar\s+kahani\s+pasand\s+aayi\s+ho,?\s*to\s+raatverse\s+ko\s+subscribe\s+karo\.?\s*kal\s+raat\s+ek\s+aur\s+nayi\s+kahani\s+milegi\.?",
        r"raatverse\s+ko\s+subscribe\s+karo\.?\s*kal\s+raat\s+ek\s+aur\s+nayi\s+kahani\s+milegi\.?",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _ensure_devanagari_subscribe_karen(source: str) -> str:
    pattern = rf"{re.escape(SUBSCRIBE_DEVANAGARI)}(?:\s+[^\s।.,!?]+)?"
    return re.sub(pattern, SUBSCRIBE_KAREN_DEVANAGARI, source, count=1)


def _normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _select_tts_source(draft: ScriptDraft, settings: Settings) -> str:
    if settings.tts_text_mode == "raw":
        return draft.narration_script

    explicit_tts_text = (draft.tts_narration_script or "").strip()
    if explicit_tts_text:
        return explicit_tts_text

    raw = draft.narration_script
    wants_devanagari = settings.tts_text_mode == "devanagari" or (
        settings.tts_use_devanagari and _is_hindi_tts_context(settings)
    )
    if wants_devanagari:
        converted = convert_hinglish_to_devanagari(raw)
        if DEVANAGARI_RE.search(converted):
            return converted
    return raw


def _is_hindi_tts_context(settings: Settings) -> bool:
    voice = settings.tts_voice.lower()
    return settings.tts_language.lower().startswith("hi") or voice.startswith("hi-in")


def _validate_tts_text(display_text: str, tts_text: str) -> list[str]:
    warnings: list[str] = []
    if not tts_text.strip():
        warnings.append("TTS text is empty.")
    if display_text and len(tts_text) < len(display_text) * 0.55:
        warnings.append("TTS text is much shorter than the display narration.")
    return warnings


def _split_long_part(part: str, max_chars: int) -> list[str]:
    words = part.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(word) > max_chars:
            chunks.extend(word[index : index + max_chars] for index in range(0, len(word), max_chars))
            current = ""
        else:
            current = word
    if current:
        chunks.append(current)
    return chunks
