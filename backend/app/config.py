"""Application settings.

Configuration is loaded from a single YAML file. The `.env` file is no longer
used — every deploy supplies `config/database.yaml` (mounted at
`/app/config/database.yaml` in the container).

Resolution order for the database section:
  1. `/app/config/database.yaml`        — production mount point
  2. `<project_root>/config/database.yaml` — dev / source-tree invocations
  3. `<project_root>/config/database.local.yaml` — local-only override
                                            (same gitignore rule as the
                                            regular file)

The YAML may reference environment variables with `${VAR}` syntax
(resolved at load time). The app refuses to start if no DB config is
found or if the password is empty — the cost of one error message is
much lower than the cost of a leaked DB credential.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BACKEND_DIR / "static"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
CONFIG_DIR = PROJECT_ROOT / "config"

# Where to read/write the master encryption key. Resolution order:
#   1. $MASTER_KEY_FILE env var (explicit override)
#   2. CWD-relative `.master_key` (works in any layout — `uvicorn` is launched
#      with WORKDIR=/app in Docker, with CWD=backend/ in dev)
#   3. PROJECT_ROOT/.master_key (fallback for source-tree invocations)
def _resolve_master_key_file() -> Path:
    env = os.environ.get("MASTER_KEY_FILE")
    if env:
        return Path(env)
    cwd_default = Path.cwd() / ".master_key"
    if cwd_default.parent.exists():
        return cwd_default
    return PROJECT_ROOT / ".master_key"


MASTER_KEY_FILE = _resolve_master_key_file()

# Hard-coded fallback inside the container (the compose file mounts
# /app/config/database.yaml, so this is the canonical location).
_CONTAINER_CONFIG = Path("/app/config/database.yaml")

# Candidate search paths, in priority order.
# The paths are part of the deploy contract between the compose file
# (which mounts `./config/database.yaml:/app/config/database.yaml:ro`)
# and the application. There is intentionally no env-var override —
# changing the in-container path is a one-line edit in two places
# (here and the volume mount), which is easy to keep in sync.
_DB_CONFIG_CANDIDATES: list[Path] = [
    _CONTAINER_CONFIG,
    CONFIG_DIR / "database.yaml",
    CONFIG_DIR / "database.local.yaml",
]

# Match ${VAR} and ${VAR:-default} inside YAML strings.
_ENV_REF_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")


def _resolve_env_refs(obj):
    """Recursively replace ${VAR} / ${VAR:-default} references in YAML values.

    Resolution rules:
      * `${VAR}`         → os.environ[VAR] if set, else raise
      * `${VAR:-default}`→ os.environ[VAR] if set, else the literal default
                           (default may be empty string)
    """
    if isinstance(obj, str):
        def repl(m: re.Match) -> str:
            var, default = m.group(1), m.group(2)
            if var in os.environ:
                return os.environ[var]
            if default is not None:
                return default
            raise ValueError(
                f"YAML references ${{{var}}} but the environment variable is not set "
                f"and no default was provided in the YAML."
            )
        return _ENV_REF_RE.sub(repl, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_refs(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_refs(v) for v in obj]
    return obj


def _find_db_config_path() -> Path | None:
    for p in _DB_CONFIG_CANDIDATES:
        if p and p.is_file():
            return p
    return None


def _load_db_config() -> dict:
    """Read the database section from the active config file.

    The YAML may contain either a top-level `database:` key (in which case
    we return its body) or a flat structure (in which case we treat the
    whole file as the DB config — common for single-purpose deploys).
    """
    path = _find_db_config_path()
    if path is None:
        raise FileNotFoundError(
            "No database config found. Create `config/database.yaml` at the "
            "project root (or mount one at /app/config/database.yaml in the "
            "container). See config/database.yaml.example for the schema."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping, got {type(raw).__name__}")
    if "database" in raw and isinstance(raw["database"], dict):
        return _resolve_env_refs(raw["database"])
    return _resolve_env_refs(raw)


class Settings(BaseSettings):
    """Application settings.

    Only server-level knobs (port, timeouts) come from environment variables
    (so the operator can still tweak them at runtime). All secrets / DB
    connection details come from `config/database.yaml`.
    """

    model_config = SettingsConfigDict(
        # NOTE: pydantic-settings still uses env vars for the fields below.
        # We intentionally do NOT point env_file at `.env` — the .env
        # mechanism is deprecated for this project. Server-level values
        # (PORT, DEBUG, etc.) can still be set via the container's
        # `environment:` block in docker-compose.yml.
        case_sensitive=False,
        extra="ignore",
    )

    # --- Server ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=9060)
    debug: bool = Field(default=False)

    # --- Storage ---
    upload_dir: Path = Field(default=UPLOAD_DIR)
    static_dir: Path = Field(default=STATIC_DIR)

    # --- External API defaults (per request, not for auth) ---
    request_timeout: float = Field(default=180.0)

    # --- Database (loaded from YAML, not from env) ---
    db: dict = Field(default_factory=_load_db_config)

    @property
    def db_dsn(self) -> str:
        """Async DSN suitable for asyncpg.

        Includes an optional `?sslmode=require` when the YAML sets
        `ssl: true`, so a managed Postgres behind TLS just works.
        """
        from urllib.parse import quote_plus
        d = self.db
        user = quote_plus(d["user"])
        pwd = quote_plus(str(d.get("password", "")))
        host = d["host"]
        port = int(d.get("port", 5432))
        name = d["name"]
        ssl = d.get("ssl")
        suffix = "?sslmode=require" if ssl else ""
        return f"postgresql://{user}:{pwd}@{host}:{port}/{name}{suffix}"

    @property
    def db_dsn_no_db(self) -> str:
        """DSN that connects to the server but not a specific database (for CREATE DATABASE)."""
        from urllib.parse import quote_plus
        d = self.db
        user = quote_plus(d["user"])
        pwd = quote_plus(str(d.get("password", "")))
        host = d["host"]
        port = int(d.get("port", 5432))
        ssl = d.get("ssl")
        suffix = "?sslmode=require" if ssl else ""
        return f"postgresql://{user}:{pwd}@{host}:{port}/postgres{suffix}"

    @model_validator(mode="after")
    def _require_db_password(self) -> "Settings":
        """Refuse to boot if the YAML is missing or has an empty password."""
        if not self.db:
            raise ValueError("Database config is empty — check config/database.yaml.")
        pwd = self.db.get("password")
        if not pwd:
            raise ValueError(
                "Database password is empty in config/database.yaml. The "
                "application refuses to start with an empty password. "
                "Set `password:` to a real value, or use `${DB_PASSWORD}` "
                "in the YAML and supply the env var."
            )
        for required in ("host", "user", "name"):
            if not self.db.get(required):
                raise ValueError(
                    f"Database config is missing required key `{required}` "
                    f"in config/database.yaml."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_dirs() -> None:
    """Make sure runtime directories exist."""
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    get_settings().static_dir.mkdir(parents=True, exist_ok=True)


def active_config_path() -> Path | None:
    """Return the path of the database config that's actually in use.

    Useful for startup logs and the `/api/health` endpoint so operators
    can see which file got loaded.
    """
    return _find_db_config_path()
