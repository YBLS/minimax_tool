# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Configuration is now YAML, not `.env`.** The app reads its database connection from `config/database.yaml` (mounted at `/app/config/database.yaml` in the container). `.env` and `.env.example` have been removed. The YAML supports `${VAR}` / `${VAR:-default}` references so the password can be supplied at runtime via env var, Docker secret, or any other injection mechanism. `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` / `DB_PORT` environment variables are no longer used; remove them from any deploy scripts. The default form is to put the password directly in the YAML (the file is gitignored, and GitHub secret scanning is the second line of defence).
- **Docker stack no longer bundles PostgreSQL.** `docker-compose.yml` ships only the `app` service; the app connects to an external Postgres 16+ configured via `config/database.yaml`. Remove the `postgres` service and `postgres_data` volume when upgrading.
- **`DB_PASSWORD` is now required at startup.** The backend refuses to boot with an empty password; the default placeholder has been removed from `backend/app/config.py`, `scripts/smoke.py`, and the previous `changeme` defaults in `.env.example` / `docker-compose.yml`.
- **README** reorganized: front matter is now use-case driven ("I want to animate a still", "I want to A/B compare models", …) instead of a project-layout tour. See `docs/ARCHITECTURE.md` for the file map.

### Added
- **`config/database.yaml.example`** — template for the new config file. Supports `${DB_PASSWORD}` (env), `${DB_PASSWORD_FILE:-/run/secrets/db_password}` (Docker secret), or a plain string. Add `pyyaml>=6.0.2` to dependencies.

## [0.1.0] - 2026-06-09

### Added

- **Modules**: image, voice, music, video (T2V / I2V / FL2V).
- **Video sub-modes**:
  - T2V (text-only), I2V (first-frame image), FL2V (first + last frame).
  - Model sub-set filter, dynamic duration × resolution matrix per (model, submode).
  - First/last frame image accepts URL or local file (drag-drop, auto base64, ≤ 20 MB).
- **Studio sidebar**: parent "Studio" + 4 children (Image / Voice / Music / Video).
- **Generation history** with full request/response payloads, output file references, status, duration.
- **Config Center**: edit / add / delete per-module configs (API key, base URL, endpoint, model, request/response templates, default params). Pre-flight **Test** button.
- **Secrets** store for reusable values referenced by `{{secrets.NAME}}` in templates.
- **Encryption**: Fernet-encrypted API keys and secrets at rest. Master key from `.master_key` or `MASTER_KEY` env var.
- **Single-port deploy**: FastAPI serves the Vite-built SPA from `backend/static/` with `Cache-Control: no-store` on `index.html`.
- **Smoke test** (`scripts/smoke.py`): 11-step regression covering SPA fallback, API contracts, write paths.
- **Template render check** (`backend/scripts/check_video_template_render.py`) covers all 4 video sub-mode bodies.
- **Docker**: `Dockerfile` + `docker-compose.yml` (app + postgres + named volume for uploads).
- **Docs**: README, USAGE, ARCHITECTURE, SECURITY.

### Models supported (current flagships)

- Image: `image-01`
- Voice: `speech-2.6-turbo`
- Music: `music-2.0`
- Video: `MiniMax-Hailuo-2.3`, `MiniMax-Hailuo-2.3-Fast`, `MiniMax-Hailuo-02`, `T2V-01-Director`, `T2V-01`, `I2V-01-Director`, `I2V-01-live`, `I2V-01`

[Unreleased]: https://github.com/<your-org>/minimax-tool/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<your-org>/minimax-tool/releases/tag/v0.1.0
