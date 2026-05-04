# Strategy Learning

Phase 6 turns analytics snapshots into category scores and script-generation guidance. It does not upload or publish anything automatically.

## Scoring

Each snapshot gets derived rates:

- `like_rate = likes / views`
- `comment_rate = comments / views`
- `subscriber_gain_rate = subscribers_gained / views`
- `retention_score = average_view_duration / target_duration`

The performance score uses configurable weights:

```env
ANALYTICS_WEIGHT_VIEWS=0.35
ANALYTICS_WEIGHT_LIKE_RATE=0.20
ANALYTICS_WEIGHT_COMMENT_RATE=0.10
ANALYTICS_WEIGHT_RETENTION=0.25
ANALYTICS_WEIGHT_SUBSCRIBERS=0.10
```

Metrics are normalized against existing channel snapshots and capped so one viral video cannot dominate the model.

## Category Scores

Run:

```bash
python -m raatverse_agent analytics update-scores
python -m raatverse_agent strategy categories
```

Category scores aggregate the latest upload-level snapshots. When both early and 7-day data exists, the default blend is:

```env
ANALYTICS_EARLY_WINDOW_WEIGHT=0.60
ANALYTICS_SEVEN_DAY_WEIGHT=0.40
```

If 7-day data is missing, available snapshots are used with lower confidence.

## Recommendations

Run:

```bash
python -m raatverse_agent strategy recommend
```

The strategy service returns:

- a human-readable summary,
- recommended weekly category distribution,
- ranked category scores,
- exploration/exploitation settings,
- hook repetition warnings,
- a machine-readable plan.

Default balance:

```env
STRATEGY_EXPLOITATION_RATE=0.70
STRATEGY_EXPLORATION_RATE=0.30
```

If horror is clearly winning, the recommendation may allocate more horror ideas for the next week while still reserving variety slots for mystery, suspense, or other categories.

## Auto Category

Generate from learned category scores:

```bash
python -m raatverse_agent script generate --auto-category --mock
python -m raatverse_agent script generate --auto-category
```

Manual override still works:

```bash
python -m raatverse_agent script generate --category mystery --mock
```

## Safety Boundary

Strategy learning only influences future draft category selection. It does not bypass script review, asset approval, render validation, or private upload approval.
