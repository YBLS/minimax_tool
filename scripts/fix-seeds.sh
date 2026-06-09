#!/usr/bin/env bash
# Idempotent seed fixer — bring the api_configs table up to date with the
# latest known-good model names, response parsers, and templates.
#
# Each underlying script is no-op if the row already matches, so this is
# safe to run on every deploy. The user's API keys are preserved.
#
# USAGE
#   Local dev:  bash scripts/fix-seeds.sh
#   In docker:  docker compose exec app bash /app/../scripts/fix-seeds.sh
#               (or: docker compose run --rm app python -m app.scripts.fix_seed_models ...)
#
# This is a *developer convenience* — production deploys shouldn't need it
# because `app/models.py:init_schema()` runs on every backend boot and the
# seed values there are always up to date. If you ran an older image once
# and got out-of-date rows, this script catches you up.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Pick the right python: host venv OR container's system python
if [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PY="$ROOT/backend/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PY="$(command -v python)"
else
  echo "No python found. Run inside the docker container: docker compose exec app python <script>" >&2
  exit 1
fi

run() {
  echo
  echo "▸ $*"
  (cd "$ROOT/backend" && "$PY" "$@")
}

run scripts/fix_seed_models.py            # image/voice/music/video model names
run scripts/fix_voice_parser.py           # voice response_parser → minimax_music
run scripts/fix_video_parser.py           # video download_method → GET
run scripts/fix_video_template.py         # video request_template 10 fields
run scripts/fix_seed_default_params.py    # music default_params has [Instrumental] lyrics

echo
echo "✓ all seeds up to date"
