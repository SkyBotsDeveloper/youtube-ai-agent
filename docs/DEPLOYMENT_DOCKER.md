# Docker Deployment

Phase 9 adds `docker-compose.prod.yml` as a production-oriented skeleton.

## Start

```bash
cp .env.example .env
python -m raatverse_agent db backup
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

The compose file:

- binds FastAPI to localhost by default,
- mounts `data/`, `outputs/`, and `secrets/`,
- keeps `AUTO_UPLOAD=false`,
- requires dashboard token configuration in production.

Use Caddy or Nginx for HTTPS and external authentication.
