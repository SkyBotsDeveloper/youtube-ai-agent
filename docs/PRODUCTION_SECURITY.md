# Production Security

The project is local-first. If the dashboard is exposed beyond localhost, add multiple layers of protection.

## Safe Defaults

```env
AUTO_UPLOAD=false
AUTO_UPLOAD_MUST_BE_APPROVED=true
CONFIRM_ENABLE_AUTO_UPLOAD=false
DASHBOARD_REQUIRE_TOKEN=false
DASHBOARD_PROTECT_READS=false
DB_BACKUP_BEFORE_UPGRADE=true
RELEASE_BACKUP_REQUIRED=true
```

`AUTO_UPLOAD=true` is treated as unsafe unless `CONFIRM_ENABLE_AUTO_UPLOAD=true` is explicitly set. The recommended production setting is still `AUTO_UPLOAD=false`.

## Dashboard Token

For remote access:

```env
DASHBOARD_REQUIRE_TOKEN=true
DASHBOARD_PROTECT_READS=true
DASHBOARD_ADMIN_TOKEN=replace-with-long-random-token
DASHBOARD_ALLOWED_HOSTS=your-domain.example
```

Use the token through a query parameter or `X-Dashboard-Token` header. Do not put the token in screenshots or logs.

## Reverse Proxy

Use HTTPS and an external auth layer such as:

- Caddy basic auth,
- Nginx basic auth,
- Cloudflare Access,
- VPN-only access.

`Caddyfile.example` shows a placeholder reverse proxy profile. Replace the domain and auth hash before use.
