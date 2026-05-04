# VPS Docker + Caddy Deployment

This is the primary production-style target for Phase 10.

## Ubuntu Setup

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin caddy
sudo usermod -aG docker $USER
```

Log out and back in after adding the Docker group.

## App Setup

```bash
git clone <your-repo-url> /opt/raatverse-agent
cd /opt/raatverse-agent
cp .env.example .env
```

Edit `.env`:

```env
APP_ENV=production
DATABASE_URL=sqlite:///./data/raatverse_agent.db
AUTO_UPLOAD=false
DASHBOARD_REQUIRE_TOKEN=true
DASHBOARD_PROTECT_READS=true
DASHBOARD_ADMIN_TOKEN=replace-with-long-random-token
DB_BACKUP_BEFORE_UPGRADE=true
RELEASE_BACKUP_REQUIRED=true
```

## Deploy

```bash
python -m raatverse_agent db safe-upgrade
docker compose -f docker-compose.prod.yml up -d --build
python -m raatverse_agent ops doctor
```

## Caddy

Copy `Caddyfile.example`, replace `your-domain.example`, and configure real basic-auth credentials.

## Backups

```cron
15 2 * * * cd /opt/raatverse-agent && scripts/backup_cron.sh >> outputs/logs/backup.log 2>&1
```

## Update Flow

```bash
git pull
python -m raatverse_agent release prepare --version <version>
python -m raatverse_agent db safe-upgrade
docker compose -f docker-compose.prod.yml up -d --build
python -m raatverse_agent ops doctor
```

## Rollback

```bash
docker compose -f docker-compose.prod.yml stop
python -m raatverse_agent db restore outputs/backups/<backup>.sqlite3 --confirm
docker compose -f docker-compose.prod.yml up -d
```
