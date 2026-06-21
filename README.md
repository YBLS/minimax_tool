# MiniMax Tool

> A compact web UI for MiniMax translation and media generation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115-009688.svg)](https://fastapi.tiangolo.com)

This version builds on v0.1 with a streamlined UI, production hardening, configurable API-key providers, and a new **Translation** module. PostgreSQL is no longer bundled: connect any reachable PostgreSQL 16+ instance through `config/database.yaml`.

## Features

- Translation with source-language detection
- Image generation
- Text-to-speech
- Music generation
- T2V, I2V, and FL2V video generation
- Encrypted API keys, redacted history, and local media storage
- Optional HTTP Basic authentication and production-safe defaults

## Quick start

Requirements: Docker with Compose v2 and PostgreSQL 16+.

```bash
git clone <repo-url> minimax-tool
cd minimax-tool
cp config/database.yaml.example config/database.yaml
$EDITOR config/database.yaml
touch .master_key && chmod 600 .master_key
docker compose up -d --build
```

Verify and open the app:

```bash
curl http://localhost:9060/api/health
# {"status":"ok","db":true,"version":"0.2.0"}
```

<http://localhost:9060>

Add a MiniMax API key under **Config Center → API Keys**, then use Translation or any Studio module.

## Video modes

- **T2V** — text to video
- **I2V** — first frame plus prompt
- **FL2V** — first and last frames plus prompt

Camera-control example:

> A man picks up a book [push in, crane up], then reads [static shot].

## Documentation

- [Usage](docs/USAGE.md)
- [Deployment](docs/DEPLOY.md)
- [Security](docs/SECURITY.md)
- [Architecture](docs/ARCHITECTURE.md)

## License

[MIT](LICENSE) © 2026 MiniMax Tool contributors.
