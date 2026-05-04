# YouTube Upload

Phase 5 adds a strict render-to-upload workflow for YouTube Data API v3. Uploads are private by default and require explicit approval.

## Mock Upload

Mock upload does not require Google credentials.

```bash
python -m raatverse_agent db init
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script approve 1
python -m raatverse_agent assets prepare 1 --mock
python -m raatverse_agent render create 1 --mock
python -m raatverse_agent youtube metadata-preview 1
python -m raatverse_agent youtube prepare-upload 1
python -m raatverse_agent youtube approve-upload 1
python -m raatverse_agent youtube upload 1 --mock
python -m raatverse_agent youtube list
```

## Real Private Upload

Configure OAuth first, then run:

```bash
python -m raatverse_agent youtube prepare-upload 1
python -m raatverse_agent youtube approve-upload 1
python -m raatverse_agent youtube upload 1
```

The real uploader uses a resumable `videos.insert` upload and sets:

- `privacyStatus=private`
- `selfDeclaredMadeForKids=false`
- `containsSyntheticMedia=true` by default
- `categoryId=24` by default

## Scheduling

Scheduled publishing is metadata-only before upload:

```bash
python -m raatverse_agent youtube schedule 1 --publish-at "2026-05-05T20:00:00+05:30"
```

or:

```bash
python -m raatverse_agent youtube schedule 1 --schedule-next
```

When scheduled, the uploader sends `status.publishAt` only with private privacy.

## Quota and Verification

YouTube Data API `videos.insert` costs 100 quota units per upload. Google also notes that uploads from unverified API projects created after July 28, 2020 may be restricted to private viewing until the project passes audit.
