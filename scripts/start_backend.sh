#!/usr/bin/env bash
# Start the MiniMax Tool backend in the background, write logs to /tmp/minimax.log.
set -e
cd "$(dirname "$0")/../backend"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 9060 --log-level info
