# Render Deployment

`render.yaml` is a safe skeleton for a Render web service.

## Notes

- Use Docker runtime.
- Keep `AUTO_UPLOAD=false`.
- Set `DASHBOARD_REQUIRE_TOKEN=true`.
- Store secrets in Render environment variables.
- Use a persistent database before relying on scheduled production state.

Render free instances can sleep, so use this profile for dashboard/API access or mock/dev operation unless persistent scheduling is configured carefully.
