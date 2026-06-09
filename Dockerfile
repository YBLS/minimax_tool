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
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /work/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build   # → ../backend/static/

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

# `app/config.py` reads .env from CWD; we set WORKDIR to /app.
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
