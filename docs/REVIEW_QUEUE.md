# Review Queue

The review queue shows what needs human action before the next stage can proceed.

## CLI

```bash
python -m raatverse_agent review queue
```

## API

```http
GET /review/queue
GET /ops/pending-review
```

## Queue Sections

- Pending script drafts: `draft` or `needs_revision` drafts waiting for approve/reject.
- Approved scripts needing assets: approved drafts that do not have an asset plan.
- Asset plans needing render: ready asset plans that do not have a render.
- Renders needing upload metadata: ready renders that do not have upload metadata.
- Upload records needing approval: `upload_pending` records.
- Analytics snapshots due: uploaded videos old enough for 24h, 48h, or 7d snapshots.

## Safety

The queue is informational. It does not bypass approval gates. YouTube upload remains private by default and upload execution still requires explicit approval.
