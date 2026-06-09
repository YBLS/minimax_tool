# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
