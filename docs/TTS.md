# TTS

Phase 3 adds narration audio preparation for approved script drafts.

## No-Paid-API Policy

The default provider is `mock`. The free online provider uses `edge-tts` and does not require an API key. Paid providers such as ElevenLabs or Google Cloud TTS are not required and are not implemented.

## Mock Mode

```bash
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script approve 1
python -m raatverse_agent tts generate 1 --mock
```

Mock mode writes a placeholder file under `TTS_CACHE_DIR` and stores timing metadata in SQLite.

## Free TTS Mode

Configure `.env`:

```env
TTS_PROVIDER=free
TTS_VOICE=hi-IN-SwaraNeural
TTS_LANGUAGE=hi-IN
TTS_SPEAKING_RATE=normal
TTS_OUTPUT_FORMAT=mp3
TTS_MAX_RETRIES=2
TTS_CACHE_DIR=./outputs/assets/audio
TTS_TEXT_MODE=auto
TTS_USE_DEVANAGARI=true
TTS_MAX_CHARS_PER_CHUNK=450
TTS_PAUSE_STYLE=punctuation
CTA_TTS_OVERRIDE=
TTS_CTA_SLOWER=true
TTS_CTA_RATE_REDUCTION=10
TTS_CTA_EXTRA_PAUSE_MS=250
```

Run:

```bash
python -m raatverse_agent tts generate 1
```

The recommended Hindi voice is `hi-IN-SwaraNeural`. `hi-IN-MadhurNeural` is available as a male alternate. The legacy aliases `female_hindi` and `male_hindi` still map to those voices. If the online provider fails, the attempt is saved as `asset_failed` with an error message.

## TTS-Friendly Hindi Text

Real Hinglish scripts are kept for display subtitles, but Hindi Edge voices pronounce Devanagari text more reliably than Roman Hindi. Script generation now asks for both:

- `narration_hinglish`: display narration and subtitles
- `narration_hindi_devanagari_for_tts`: narration sent to Hindi TTS voices

When no explicit Devanagari field exists, `TTS_TEXT_MODE=auto` uses a local normalization pass to improve common Roman Hindi words before sending text to edge-tts. This is a best-effort helper, not a full translation system.

## CTA Pronunciation

Hindi neural voices can pronounce the Roman word `subscribe` inconsistently. The TTS pipeline keeps the visible Hinglish CTA for subtitles, but replaces the spoken CTA with a clearer Hindi/Devanagari variant for TTS:

```text
अगर कहानी पसंद आई हो, तो रातवर्स चैनल को सब्सक्राइब ज़रूर करें। कल रात एक और नई कहानी मिलेगी।
```

To override only the spoken CTA text:

```env
CTA_TTS_OVERRIDE=अगर कहानी पसंद आई हो, तो रातवर्स चैनल को सब्सक्राइब ज़रूर करें। कल रात एक और नई कहानी मिलेगी।
```

If `TTS_CTA_SLOWER=true`, the edge-tts adapter speaks CTA chunks with a slightly slower rate using `TTS_CTA_RATE_REDUCTION`. `TTS_CTA_EXTRA_PAUSE_MS` is represented as punctuation pauses in the CTA text so the phrase stays clearer without affecting the story narration.

Before edge-tts receives text, the app:

- normalizes punctuation and repeated ellipses
- adds natural punctuation pauses
- splits long narration into chunks using `TTS_MAX_CHARS_PER_CHUNK`
- preserves all text content instead of silently dropping long paragraphs

The generated `audio_assets` record stores the final `tts_text`, chunk list, and quality metadata. CLI output reports input characters, chunk count, duration, and warnings.

When `ffprobe` is available through the local FFmpeg install, the free TTS provider probes the generated audio file and stores the actual duration. Render timing then uses that duration as the source of truth so subtitles and scene beats are scaled to the spoken audio instead of only the script estimate.

For subtitle sync, edge-tts boundary events are captured when the provider exposes them. The app stores boundary metadata and chunk timing metadata in `tts_quality_metadata`, then uses those timings to align subtitle lines in narration order.

## Stored Audio Metadata

The `audio_assets` table stores:

- script draft ID
- provider
- voice
- language
- file path
- estimated duration
- TTS text used for generation
- TTS chunks sent to the provider
- TTS quality metadata and warnings
- subtitle timing JSON
- scene timing JSON
- status
- error message
- created time
