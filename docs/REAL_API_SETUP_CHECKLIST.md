# Real API Setup Checklist

Use this only after mock mode is stable.

## Script Generation

- Set `LLM_PROVIDER`.
- Set `LLM_API_KEY`.
- Set `LLM_MODEL`.
- Keep generated scripts in draft status for review.

## Free TTS and Stock Media

- Use free `edge-tts` or mock.
- Add optional Pexels/Pixabay keys only if needed.
- Keep attribution metadata.

## YouTube

- Enable YouTube Data API v3.
- Enable YouTube Analytics API.
- Configure OAuth scopes.
- Store token file under ignored `secrets/`.
- Upload private by default.

## Safety

```env
AUTO_UPLOAD=false
UPLOAD_PRIVACY_STATUS=private
AUTO_UPLOAD_MUST_BE_APPROVED=true
```

Do not enable public auto-upload.
