"""Application settings loaded from environment variables.

We intentionally keep this file minimal — secrets are read from the database
at runtime, not from config files. The only "secret" needed at boot is the
master encryption key, which can come from either:
  1. A `.master_key` file in the project root (auto-generated on first run), or
  2. The `MASTER_KEY` environment variable (preferred for production).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BACKEND_DIR / "static"
UPLOAD_DIR = PROJECT_ROOT / "uploads"

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


class Settings(BaseSettings):
    """Application settings — all values overridable via env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Server ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=9060)
    debug: bool = Field(default=False)

    # --- Database ---
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)
    db_user: str = Field(default="postgres")
    db_password: str = Field(default="p@ssw0rd")
    db_name: str = Field(default="minimax_tool")

    # --- Storage ---
    upload_dir: Path = Field(default=UPLOAD_DIR)
    static_dir: Path = Field(default=STATIC_DIR)

    # --- External API defaults (per request, not for auth) ---
    request_timeout: float = Field(default=180.0)

    @property
    def db_dsn(self) -> str:
        """Async DSN suitable for asyncpg."""
        return (
            f"postgresql://{self.db_user}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def db_dsn_no_db(self) -> str:
        """DSN that connects to the server but not a specific database (for CREATE DATABASE)."""
        return (
            f"postgresql://{self.db_user}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/postgres"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_dirs() -> None:
    """Make sure runtime directories exist."""
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    get_settings().static_dir.mkdir(parents=True, exist_ok=True)
