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
TTS_VOICE=female_hindi
TTS_LANGUAGE=hi-IN
TTS_SPEAKING_RATE=normal
TTS_OUTPUT_FORMAT=mp3
TTS_MAX_RETRIES=2
TTS_CACHE_DIR=./outputs/assets/audio
```

Run:

```bash
python -m raatverse_agent tts generate 1
```

The free provider maps `female_hindi` to `hi-IN-SwaraNeural` and `male_hindi` to `hi-IN-MadhurNeural`. If the online provider fails, the attempt is saved as `asset_failed` with an error message.

## Stored Audio Metadata

The `audio_assets` table stores:

- script draft ID
- provider
- voice
- language
- file path
- estimated duration
- subtitle timing JSON
- scene timing JSON
- status
- error message
- created time
