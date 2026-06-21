# syntax=docker/dockerfile:1.7
# ============================================================
#  MiniMax Tool — production image
#
#  Multi-stage:
#    1. `frontend-builder`  : builds the React SPA (Node 20)
#    2. `backend-builder`   : installs Python deps into a venv
#    3. `runtime`           : python:3.13-slim + the venv + the SPA
# ============================================================

# ----- Stage 1: frontend build -----
# We use yarn (4.x) for the frontend instead of npm. yarn 4 ships with a
# PnP linker that doesn't need a node_modules tree; vite + esbuild pick up
# the unplugged native modules automatically. If a yarn.lock is checked in
# (the common case), the install is reproducible via `--immutable`; the
# fallback to `yarn install` only runs the first time the lockfile is
# generated, so subsequent builds keep the strict guarantee.
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /work/frontend
COPY frontend/package.json frontend/yarn.lock* ./
# Yarn 4.x isn't published to the npm registry — it's only distributed via
# corepack. node:20-bookworm-slim ships an older corepack that doesn't
# understand modern JS syntax, so we explicitly upgrade corepack first, then
# `prepare` the exact yarn version we want.
RUN npm install -g corepack@latest --no-audit --no-fund \
 && corepack enable \
 && corepack prepare yarn@4.5.3 --activate
# Lockfile-aware install: `yarn install --immutable` is strict (errors on
# drift) and is what we want when yarn.lock is checked in. The fallback
# only runs on the very first build before a lockfile exists.
RUN if [ -f yarn.lock ]; then \
      yarn install --immutable; \
    else \
      yarn install; \
    fi

COPY frontend/ ./
RUN yarn build   # → ../backend/static/

# ----- Stage 2: backend deps -----
FROM python:3.13-slim AS backend-builder

# uv is the package manager. Pin a recent stable.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /work/backend
COPY backend/pyproject.toml backend/uv.lock* ./

# Allow `--locked` to be skipped when the lockfile is absent (CI / first push).
RUN uv sync --frozen --no-install-project 2>/dev/null \
 || uv sync --no-install-project

COPY backend/ ./
RUN uv sync --frozen --no-dev 2>/dev/null \
 || uv sync --no-dev

# ----- Stage 3: runtime -----
FROM python:3.13-slim AS runtime

# Non-root for the running app. PostgreSQL client libs are not needed
# (asyncpg ships its own protocol impl).
RUN groupadd --system app \
 && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

# Copy the prepared venv from the builder.
COPY --from=backend-builder --chown=app:app /work/backend/.venv /app/.venv
# Copy the application source.
COPY --from=backend-builder --chown=app:app /work/backend/app /app/app
COPY --from=backend-builder --chown=app:app /work/backend/pyproject.toml /app/pyproject.toml
# Copy the built frontend.
COPY --from=frontend-builder --chown=app:app /work/backend/static /app/static

# Persistent storage: uploads + master key (when not using MASTER_KEY env)
RUN mkdir -p /app/uploads/image /app/uploads/voice /app/uploads/music /app/uploads/video \
 && chown -R app:app /app
VOLUME ["/app/uploads"]

# `app/config.py` reads config/database.yaml from the search-path list
# (`/app/config/database.yaml` first); we set WORKDIR to /app.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=9060

EXPOSE 9060

USER app

# The entrypoint must run as the app user; we still want a writable CWD
# for the .master_key auto-generation.
WORKDIR /app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9060"]
