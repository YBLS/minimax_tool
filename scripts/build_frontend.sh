#!/usr/bin/env bash
# Build the React frontend using a Node version compatible with vite 4+.
# Tries Homebrew Node 18+ first, falls back to whatever is in PATH.

set -e
cd "$(dirname "$0")/../frontend"

if [ -x /opt/homebrew/bin/node ]; then
  NODE_BIN=/opt/homebrew/bin/node
  NPM_BIN=/opt/homebrew/bin/npm
elif command -v node >/dev/null 2>&1; then
  NODE_BIN=$(command -v node)
  NPM_BIN=$(command -v npm)
else
  echo "[build_frontend] No node found. Install Node 18+ first." >&2
  exit 1
fi

NODE_MAJOR=$("$NODE_BIN" -p 'process.versions.node.split(".")[0]')
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "[build_frontend] Found Node $("$NODE_BIN" --version) — need 18+." >&2
  exit 1
fi

echo "[build_frontend] using $($NODE_BIN --version)"
"$NPM_BIN" install --no-audit --no-fund
"$NPM_BIN" run build
echo "[build_frontend] done."
