from __future__ import annotations

import re
from dataclasses import dataclass

from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

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


def prepare_tts_text(draft: ScriptDraft, settings: Settings) -> PreparedTTSText:
    display_text = draft.narration_script.strip()
    source = _select_tts_source(draft, settings)
    normalized = normalize_tts_text(source, settings)
    chunks = chunk_tts_text(normalized, settings.tts_max_chars_per_chunk)
    warnings = _validate_tts_text(display_text, normalized)
    return PreparedTTSText(
        display_text=display_text,
        tts_text=normalized,
        chunks=chunks,
        original_characters=len(display_text),
        input_characters=len(normalized),
        warnings=warnings,
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
