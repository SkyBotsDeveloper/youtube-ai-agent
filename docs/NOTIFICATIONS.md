# Notifications

Phase 8 adds notification hooks without requiring any paid service.

## Providers

- `mock`: local/offline provider used by tests and dry runs.
- `webhook`: generic HTTP webhook provider.

Default config:

```env
NOTIFICATIONS_ENABLED=false
NOTIFICATION_PROVIDER=mock
NOTIFICATION_WEBHOOK_URL=
NOTIFY_ON_DRAFT_CREATED=true
NOTIFY_ON_WORKFLOW_FAILED=true
NOTIFY_ON_UPLOAD_READY=true
NOTIFY_ON_ANALYTICS_READY=true
```

## Test

```bash
python -m raatverse_agent notify test --mock
```

Real webhook test:

```env
NOTIFICATIONS_ENABLED=true
NOTIFICATION_PROVIDER=webhook
NOTIFICATION_WEBHOOK_URL=https://example.com/raatverse-webhook
```

```bash
python -m raatverse_agent notify test
```

If webhook mode is selected without `NOTIFICATION_WEBHOOK_URL`, the command fails gracefully with a clear error.

## Workflow Events

Notification hooks are wired for:

- draft created,
- workflow failed,
- upload metadata ready for approval,
- analytics due workflow completed.

Notifications do not change approval gates and do not upload videos.
