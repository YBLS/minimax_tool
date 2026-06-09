#!/usr/bin/env bash
# Install backend deps + initialize DB + build frontend + start server.

set -e
cd "$(dirname "$0")/.."

echo "==> [1/4] uv sync (Python 3.13 + backend deps)"
(cd backend && uv sync)

echo "==> [2/4] init PostgreSQL schema (idempotent)"
(cd backend && uv run python scripts/init_db.py)

echo "==> [3/4] build frontend (idempotent)"
bash scripts/build_frontend.sh

echo "==> [4/4] start uvicorn on 0.0.0.0:9060"
exec uv --project backend run -- python -m uvicorn app.main:app --host 0.0.0.0 --port 9060
