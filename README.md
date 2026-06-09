# MiniMax Tool

> Local web UI for the MiniMax AI platform — image / voice / music / video generation, with **all API keys encrypted at rest** in a self-hosted PostgreSQL.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115-009688.svg)](https://fastapi.tiangolo.com)

## Why this exists

Calling MiniMax's generation APIs from a terminal works, but the moment you want to:

- A/B compare **image / voice / music / video** side-by-side
- Remember **which model / endpoint** worked best for what
- Re-run the same call with a small tweak
- Keep your **API keys out of source control and shell history**

…you start writing a tiny UI. That's what this is. One binary, one port, one database, and your keys are encrypted with Fernet before they ever touch disk.

## Features

| Module | Sub-modes | Models (current flagships) |
|--------|-----------|------------------------------|
| **Image** | — | `image-01` |
| **Voice** (TTS) | — | `speech-2.6-turbo` (32 languages, 100+ presets) |
| **Music** | — | `music-2.0` (up to 4 min) |
| **Video** | **T2V** / **I2V** / **FL2V** | `MiniMax-Hailuo-2.3`, `MiniMax-Hailuo-02`, plus legacy `T2V-01*` / `I2V-01*` |

- 🖼 Generate, preview, and download every artifact (saved under `uploads/<module>/YYYY/MM/DD/`)
- 🔐 **API keys encrypted** with Fernet (AES-128-CBC + HMAC-SHA256) before storage
- 🧠 **Per-call parameter tables** (aspect ratio, voice, duration, resolution, first/last frame image, etc.)
- 📜 **Generation history** with full request/response payloads (truncated for legibility)
- 🔁 **Reset to config defaults** with one click
- 🩺 **Health check** + smoke test (`scripts/smoke.py`) covers SPA, API contracts, write paths
- 🐳 **One-command deploy** with `docker compose up`

## Quick start (Docker, recommended)

```bash
git clone https://github.com/<your-org>/minimax-tool.git
cd minimax-tool

# Optional: edit the .env to set DB password / ports
cp .env.example .env

docker compose up --build
```

Open <http://localhost:9060>. The app auto-creates the database, seeds the 4 default module configs, and serves the SPA.

> Generated files land in a Docker volume mounted at `/app/uploads`. To persist them across `docker compose down`, leave the volume named `minimax_uploads` in `compose.yml` (default).
>
> After changing frontend code, run `docker compose build --no-cache app && docker compose up -d` so the new bundle is baked into the image. `docker compose restart` alone is not enough.

## Quick start (local, without Docker)

Requires: **Python 3.13+**, **Node 20+**, **PostgreSQL 16+** running on `localhost:5432`.

```bash
# 1. Backend
cd backend
uv sync                     # or: pip install -e .
cp ../.env.example ../.env  # adjust DB_* if needed
uv run python scripts/init_db.py
uv run uvicorn app.main:app --host 0.0.0.0 --port 9060

# 2. Frontend (separate terminal)
cd ../frontend
npm install
npm run build               # or: npm run dev for hot-reload on :5173
# build output → ../backend/static/  (served by FastAPI on :9060)
```

Then open <http://localhost:9060>.

## First-time configuration

1. Open <http://localhost:9060> → left sidebar → **Config Center**
2. Pick a module → **Edit** → paste your MiniMax API key
3. Click **Save**. The key is encrypted immediately; the textarea clears.
4. Switch to **Studio** in the sidebar → pick **Image / Voice / Music / Video** → hit **Generate**.

Need a different model than the default? Edit the **Model** field in Common settings, or pick one in the Studio's Parameters pane (only for modules that ship multiple model options).

See **[docs/USAGE.md](docs/USAGE.md)** for module-by-module walkthroughs, including the 3 video sub-modes.

## How secrets are handled

- API keys live in PostgreSQL as `api_key_encrypted TEXT` (Fernet ciphertext, not plaintext)
- The **master key** is stored in `.master_key` (mode `0600`) at the project root, **or** supplied via the `MASTER_KEY` env var
- The first time the backend starts without a master key, it auto-generates one and refuses to log it
- **If you lose `.master_key`, your stored API keys are unrecoverable** — keep a backup
- See **[docs/SECURITY.md](docs/SECURITY.md)** for the rotation procedure, the audit checklist before going public, and what to back up.

## Project layout

```
minimax-tool/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI factory
│   │   ├── config.py            # pydantic settings
│   │   ├── crypto.py            # Fernet encrypt/decrypt
│   │   ├── database.py          # asyncpg pool
│   │   ├── models.py            # SQL schema + seed configs
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── routers/             # FastAPI routers (api endpoints)
│   │   ├── services/
│   │   │   └── generator.py     # unified request/response engine
│   │   └── utils/
│   │       └── files.py         # upload paths, media URL helpers
│   ├── scripts/                 # one-shot data fixers
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── api/client.ts
│   │   ├── pages/               # Studio, ConfigCenter, History, Secrets
│   │   ├── pages/configForms/   # ImageForm / VoiceForm / MusicForm / VideoForm
│   │   ├── styles/index.css
│   │   └── types/index.ts
│   ├── package.json
│   └── vite.config.ts
├── scripts/                     # project-level dev scripts
│   ├── smoke.py                 # 11-step regression test (host)
│   ├── smoke_docker.py          # 12-step regression test (in-container)
│   ├── fix-seeds.sh             # idempotent seed-data updater
│   ├── start_backend.sh
│   ├── build_frontend.sh
│   └── serve.sh
├── docs/
│   ├── USAGE.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOY.md
│   └── SECURITY.md
├── uploads/                     # generated artifacts (gitignored)
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── CHANGELOG.md
```

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Liveness + DB connectivity |
| `GET` | `/api/configs` | List all module configs |
| `GET` | `/api/configs/{module}` | Fetch one |
| `POST` | `/api/configs` | Create a new config |
| `PUT` | `/api/configs/{id}` | Update (passing `api_key: ""` clears it) |
| `DELETE` | `/api/configs/{id}` | Delete |
| `POST` | `/api/configs/{id}/test` | Test connectivity (no real generation) |
| `POST` | `/api/generate/{module}` | Generate (returns a result + persisted history row) |
| `GET` | `/api/history` | Recent generations (newest first) |
| `GET` | `/api/history/{id}` | Full detail (request/response payloads) |
| `DELETE` | `/api/history/{id}` | Remove a row |
| `GET` | `/api/secrets` | List app-level secrets (metadata only) |
| `PUT` | `/api/secrets/{name}` | Upsert a secret |
| `DELETE` | `/api/secrets/{name}` | Remove |
| `GET` | `/api/media/{path:path}` | Serve generated files (under `uploads/`) |

OpenAPI docs at <http://localhost:9060/docs>.

## Testing

```bash
# 11-step smoke test (covers SPA, contracts, write paths)
uv run python scripts/smoke.py

# 12-step in-container smoke (use after `docker compose up -d`)
docker compose exec -T app sh -c 'cat > /tmp/s.py' < scripts/smoke_docker.py
docker compose exec -T app python /tmp/s.py

# Pure-template render check for the 4 video sub-modes
uv run python backend/scripts/check_video_template_render.py
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `API key is empty` error | Open **Config Center** → paste your key → **Save** |
| `Upstream rejected request (base_resp.code=2013)` | Check the **Parameters** pane — for music-2.0 `lyrics` is required; for I2V/FL2V the image field is required |
| Browser shows stale UI | Hard-reload (Cmd/Ctrl+Shift+R). `index.html` is served `Cache-Control: no-store`. |
| Port 9060 in use | Set `PORT=9061` in `.env` |
| Lost `.master_key` | All encrypted API keys in DB are unrecoverable. Re-paste them. |
| `Module 'video' status: usage limit exceeded (3/3 used)` | Wait for the daily reset (MiniMax Token Plan, 00:00 UTC+8) |
| `osascript`-related errors in `mavis-trash` | Unrelated to MiniMax Tool; only affects our trash-replacement utility |

## Contributing

PRs welcome. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the local dev loop, the smoke test, and the change-log convention.

## License

[MIT](LICENSE) © 2026 MiniMax Tool contributors.
