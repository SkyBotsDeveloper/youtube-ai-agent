# Asset Workflow

Phase 3 prepares assets for an approved `ScriptDraft`. It does not perform final rendering or upload.

## Workflow

1. Generate a script draft.
2. Approve the draft.
3. Generate narration audio.
4. Search/select media candidates for each scene beat.
5. Save an `AssetPlan`.
6. Review the plan before rendering.
7. Render a local preview/output file from the approved asset plan.

## Commands

```bash
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script approve 1
python -m raatverse_agent tts generate 1 --mock
python -m raatverse_agent assets prepare 1 --mock
python -m raatverse_agent assets list
python -m raatverse_agent assets show 1
python -m raatverse_agent render create 1 --mock
```

Drafts must be approved before TTS or asset preparation. Use `--force` only for local testing.

## Statuses

- `asset_pending`: created or queued state.
- `asset_ready`: audio/media metadata is ready for review.
- `asset_failed`: provider or validation failure was captured.

## Timing Metadata

Phase 3 creates rough line-level subtitle timing and scene timing suggestions. Word-level alignment is intentionally deferred.

## Rejected Draft Regeneration

```bash
python -m raatverse_agent script reject 1 --reason "Too predictable."
python -m raatverse_agent script regenerate 1 --mock
```

Regeneration creates a new draft using the same category/story type and includes the rejection reason in the prompt seed. The old rejected draft is not overwritten.
