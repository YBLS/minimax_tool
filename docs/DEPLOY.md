# Deploying with Docker

`docker compose` brings up the app container. **You bring your own PostgreSQL
16+** — the app talks to any reachable Postgres instance and the Compose file
does not bundle a database anymore.

## Configuration: a single YAML file

All connection details — host, port, user, **password**, name, ssl,
pool tuning — live in **`config/database.yaml`** (a single YAML
file). The Compose file mounts the YAML read-only into the container
at `/app/config/database.yaml`; the app reads it on startup and
refuses to boot if it's missing or the password is empty.

The default form has the password in the YAML. Two indirection
options are also supported via `${VAR}` / `${VAR:-default}` references
(see "Supplying the password" below) for users who want to keep the
password out of the file.

## Prerequisites

- Docker Engine 20.10+ with the Compose v2 plugin (`docker compose`, not `docker-compose`)
- A reachable PostgreSQL 16+ instance (local, sidecar, managed, etc.)
- Outbound HTTPS to `https://api.minimaxi.com` (the MiniMax API)
- Python 3.13 (only for the optional smoke test)

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

# 3. Create the database config from the template and fill in the
#    real values. The default form has the password inline; the
#    file is gitignored so it stays out of git.
cp config/database.yaml.example config/database.yaml
$EDITOR config/database.yaml      # set host / user / password / name

# 4. Build and start
docker compose up -d --build

# 5. Verify
docker compose ps                  # app container healthy
curl http://localhost:9060/api/health
# → {"status":"ok","db":true,"version":"0.2.0"}
```

The SPA is at <http://localhost:9060>. Compose binds it to `127.0.0.1`
by default, so it is not reachable directly from another machine.

## Self-contained PostgreSQL 18 stack

For a bundled database, use `docker-compose.pg18.yml` instead of the default
external-database stack:

```bash
cp config/database.pg18.yaml.example config/database.pg18.yaml
touch .master_key && chmod 600 .master_key
export POSTGRES_PASSWORD='replace-with-a-strong-password'
docker compose -f docker-compose.pg18.yml up -d --build
```

The default named volumes are `minimax_pg18_data` and `minimax_uploads`.
Override their Docker names with `PG_VOLUME_NAME` / `UPLOAD_VOLUME_NAME`, or
set `PG_DATA_PATH` / `UPLOAD_DATA_PATH` to absolute host paths for bind mounts.
PostgreSQL 18 uses `/var/lib/postgresql` as its persistent mount point.

## Built-in production authentication

Set both variables before starting the stack. Browsers display their native
login dialog; API clients send the same HTTP Basic credentials.

```bash
export APP_USERNAME=minimax-admin
export APP_PASSWORD="$(openssl rand -base64 32)"   # save this in your password manager
docker compose up -d --build
```

`/api/health` intentionally remains unauthenticated for container and load
balancer health checks. Use TLS at the reverse proxy: Basic credentials must
never travel over plaintext on an untrusted network.

For a same-host reverse proxy, keep the localhost binding. To bind deliberately
to another interface, set `BIND_ADDRESS`, and set `ALLOWED_ORIGINS` to a
comma-separated list of exact HTTPS origins when cross-origin API access is needed.

## What's where

| Path (host) | Path (in container) | Purpose |
|-------------|---------------------|---------|
| `config/database.yaml` | `/app/config/database.yaml` (ro) | DB connection (host, port, user, password, name, pool, ssl) |
| `.master_key` | `/app/.master_key` | Fernet key for at-rest encryption |
| `uploads/` (volume) | `/app/uploads/` | Generated images / voice / music / video |
| (your external Postgres) | — | Database files — managed by you, not by Compose |

> `config/database.yaml`, `.master_key`, and the `minimax_uploads`
> volume are persistent across `docker compose down` / `up` cycles.
> Your external Postgres is unaffected by `docker compose down`.

## Supplying the password

Three options, in increasing complexity:

1. **Inline in the YAML** (default — simplest):
   ```yaml
   password: "your-strong-password"
   ```
   The file is gitignored, so the password stays out of git. GitHub
   secret scanning will alert you if it ever lands in a commit. This
   is fine for a single-host personal tool.

2. **Reference + env var** (handy for CI / production):
   ```yaml
   password: "${DB_PASSWORD}"
   ```
   Then `export DB_PASSWORD=...` in the shell (or inject from your
   secret manager). The YAML is safe to commit; the password lives
   in the secret manager.

3. **Reference + Docker secret** (most secure for swarm / k8s-style):
   ```yaml
   password: "${DB_PASSWORD_FILE:-/run/secrets/db_password}"
   ```
   Add a `secrets:` block to `docker-compose.yml` and mount the
   file at `/run/secrets/db_password`. The password is never in
   an environment variable or in any committed file.

## Day-to-day commands

```bash
# Tail logs
docker compose logs -f app

# Open a shell inside the app container
docker compose exec app sh

# Inspect the database config as the app sees it
docker compose exec app python -c "from app.config import get_settings, active_config_path; s = get_settings(); print('config:', active_config_path()); print('host:', s.db['host'], 'name:', s.db['name'])"

# Restart after changing the Dockerfile or requirements
docker compose build --no-cache app
docker compose up -d

# Restart after changing the frontend code
# (a rebuild is required — see "Frontend rebuilds" below)
docker compose build --no-cache app
docker compose up -d

# Stop everything (keeps the uploads volume + host .master_key + database.yaml)
docker compose down

# Nuke everything this Compose file owns (uploads + master key)
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
# 1. Database dump — read host/port/user/db straight from the YAML
#    so the backup script and the app can never disagree.
DB_HOST=$(yq '.database.host' config/database.yaml)
DB_PORT=$(yq '.database.port' config/database.yaml)
DB_USER=$(yq '.database.user' config/database.yaml)
DB_NAME=$(yq '.database.name' config/database.yaml)
pg_dump -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME" > backup-$(date +%F).sql

# 2. Master key (already in your project root, but copy to a separate safe place)
cp .master_key .master_key.bak

# 3. Database YAML (mostly for reproducibility, not a secret once
#    the password is exported as DB_PASSWORD).
cp config/database.yaml config/database.yaml.bak

# Store the files in DIFFERENT places.
```

To restore on a fresh host:

```bash
# 1. Drop the master key in place
cp .master_key.bak .master_key
chmod 600 .master_key

# 2. Restore the DB
cat backup-2026-06-09.sql | psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME"

# 3. Restore the YAML
cp config/database.yaml.bak config/database.yaml

# 4. Start
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
- [ ] Set a strong password in `config/database.yaml` (the file is gitignored; rotate the underlying Postgres user password periodically and update the YAML to match)
- [ ] Set `APP_USERNAME` and a random `APP_PASSWORD`
- [ ] Put the app behind a reverse proxy (Caddy, nginx) with TLS
- [ ] Mount the `.master_key`, the `config/database.yaml`, and the externally-hosted Postgres data dir onto a backup target
- [ ] Set up log aggregation (the app logs to stdout, so any docker-log driver works)
- [ ] Keep `BIND_ADDRESS=127.0.0.1`; only change it deliberately
- [ ] Set `ALLOWED_ORIGINS` only when a separate frontend origin is required
- [ ] Keep `ALLOW_PRIVATE_UPSTREAMS=false` and tune `MAX_DOWNLOAD_BYTES`

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Container minimax-app-1 Restarting` | `Permission denied` on `/app/.master_key` or upstream error | `docker compose logs app` to see the trace |
| `No database config found` on startup | `config/database.yaml` is missing or mounted incorrectly | Confirm the file exists at the host path shown in the volumes section, then `docker compose config` to see the resolved mount |
| `Database password is empty` on startup | The YAML has `password: ""`, or `${DB_PASSWORD}` is unset | Either paste the password in the YAML, or `export DB_PASSWORD=...` before `docker compose up` (if the YAML uses `${DB_PASSWORD}`) |
| `Connection refused` to Postgres | External DB is not reachable from the app container | Check `database.host` in `config/database.yaml`; from inside the container, `docker compose exec app sh -c 'nc -zv <host> <port>'` |
| `Address already in use` on port 9060 | Another process on the host owns the port | `lsof -nP -i:9060 -t | xargs kill -9`, or change `PORT` in `docker-compose.yml` |
| Stale UI after a frontend change | Image not rebuilt | `docker compose build --no-cache app && docker compose up -d` |
| All stored API keys become unreadable | `.master_key` file was deleted or replaced | Restore the master key from backup. Otherwise, re-paste each API key. |
| `FATAL: password authentication failed` for `postgres` | The password in `config/database.yaml` doesn't match the Postgres user | Update `config/database.yaml` to match, or change the Postgres user's password to match |
