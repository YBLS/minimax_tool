# Deploying with Docker

The fastest way to run MiniMax Tool in production-like conditions. `docker compose` brings up the app + Postgres + a persistent upload volume, all on a single host.

## Prerequisites

- Docker Engine 20.10+ with the Compose v2 plugin (`docker compose`, not `docker-compose`)
- 2 GB free disk for the Postgres data volume
- Outbound HTTPS to `https://api.minimaxi.com` (the MiniMax API)

## First-time setup (5 steps)

```bash
# 1. Clone
git clone https://github.com/<your-org>/minimax-tool.git
cd minimax-tool

# 2. Create the host master-key file. The container will see it as
#    /app/.master_key, write a fresh Fernet key on first run, and
#    bind-mount the change back to the host.
touch .master_key
chmod 600 .master_key

# 3. (Optional) Edit the .env to set DB password / ports / timezone.
cp .env.example .env
$EDITOR .env

# 4. Build and start
docker compose up -d --build

# 5. Verify
docker compose ps                  # both containers healthy
curl http://localhost:9060/api/health
# → {"status":"ok","db":true,"version":"0.1.0"}
```

The SPA is at <http://localhost:9060>.

## What's where

| Path (host) | Path (in container) | Purpose |
|-------------|---------------------|---------|
| `.env` | `/app/.env` | All settings (DB, port, master key override) |
| `.master_key` | `/app/.master_key` | Fernet key for at-rest encryption |
| `uploads/` (volume) | `/app/uploads/` | Generated images / voice / music / video |
| (Docker volume `minimax_postgres_data`) | `/var/lib/postgresql/data` | Database files |

> All of the above are persistent across `docker compose down` / `up` cycles, **except** the `postgres_data` named volume, which is *only* removed if you run `docker compose down -v`.

## Day-to-day commands

```bash
# Tail logs
docker compose logs -f app

# Open a shell inside the app container
docker compose exec app sh

# Restart after changing the Dockerfile or requirements
docker compose build --no-cache app
docker compose up -d

# Restart after changing the frontend code
# (a rebuild is required — see "Frontend rebuilds" below)
docker compose build --no-cache app
docker compose up -d

# Stop everything (keeps volumes)
docker compose down

# Nuke everything (wipes DB + uploads + master key)
docker compose down -v
rm -f .master_key
```

## Frontend rebuilds

The Vite build output is baked into the Docker image at build time. `docker compose restart` does **not** pick up frontend code changes — you need to rebuild:

```bash
# After editing files under frontend/
docker compose build --no-cache app
docker compose up -d
```

For a fast iteration loop, run the Vite dev server on the host and point it at the containerized backend:

```bash
cd frontend
npm run dev    # http://localhost:5173, proxying /api → :9060
```

The `vite.config.ts` already sets up the proxy.

## Backing up

```bash
# 1. Database dump
docker compose exec postgres pg_dump -U postgres minimax_tool > backup-$(date +%F).sql

# 2. Master key (already in your project root, but copy to a separate safe place)
cp .master_key .master_key.bak

# Store the two files in DIFFERENT places.
```

To restore on a fresh host:

```bash
# 1. Drop the master key in place
cp .master_key.bak .master_key
chmod 600 .master_key

# 2. Restore the DB
cat backup-2026-06-09.sql | docker compose exec -T postgres psql -U postgres minimax_tool

# 3. Start
docker compose up -d
```

## Updating to a new version

```bash
git pull
docker compose build
docker compose up -d
```

Schema migrations run automatically on app startup (idempotent). Seed configs are also applied automatically — but they **do not overwrite** rows you already customized (your API keys, model overrides, etc., are preserved).

If a new release changes the *shape* of a seed config (e.g. adds a field to the request template), run `scripts/fix-seeds.sh` once to bring existing rows up to date. The user's `api_key_encrypted` and any customizations are preserved.

## Production hardening checklist

- [ ] **Set an explicit `MASTER_KEY` env var** in `docker-compose.yml` so the key is not generated into a host file. Generate with:
      `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Change `DB_PASSWORD` from the default `changeme`
- [ ] Put the app behind a reverse proxy (Caddy, nginx) with TLS + basic auth
- [ ] Mount the `.master_key` and `postgres_data` volumes onto a backup target
- [ ] Set up log aggregation (the app logs to stdout, so any docker-log driver works)
- [ ] Restrict the SPA's CORS allow-origin to your reverse-proxy's host (in `backend/app/main.py`)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Container minimax-app-1 Restarting` | `Permission denied` on `/app/.master_key` or upstream error | `docker compose logs app` to see the trace |
| `Connection refused` to Postgres | App started before DB was ready | `depends_on: condition: service_healthy` already covers this; check the postgres healthcheck output |
| `Address already in use` on port 9060 | Another process on the host owns the port | `lsof -nP -i:9060 -t | xargs kill -9`, or change `PORT` in `.env` |
| Stale UI after a frontend change | Image not rebuilt | `docker compose build --no-cache app && docker compose up -d` |
| All stored API keys become unreadable | `.master_key` file was deleted or replaced | Restore the master key from backup. Otherwise, re-paste each API key. |
| `FATAL: password authentication failed` for `postgres` | DB password changed after first init | Either revert to the original password, or wipe the volume (`docker compose down -v`) |
