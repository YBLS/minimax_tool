"""Symmetric encryption helper for at-rest secrets.

We use Fernet (AES-128-CBC + HMAC-SHA256, authenticated). The master key:
  1. Is read from $MASTER_KEY env var if set, OR
  2. Is read from `.master_key` file in the project root, OR
  3. Is auto-generated on first run and persisted to `.master_key` (0600).

The master key file is git-ignored. If the file is lost, encrypted DB
records become irrecoverable — a warning is printed on every startup.
"""

from __future__ import annotations

import os
import warnings
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import MASTER_KEY_FILE


def _load_or_create_master_key(path: Path) -> bytes:
    """Return the master Fernet key, generating one if missing.

    The file is created with 0600 permissions on POSIX systems.
    """
    if env_key := os.environ.get("MASTER_KEY"):
        return env_key.encode("utf-8")

    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes().strip()

    # Either the file is missing or it's an empty placeholder (e.g. the
    # `touch master_key && chmod 600` a Docker user does before `compose up`).
    # Generate a fresh key and persist it.
    key = Fernet.generate_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        # On Windows / some filesystems chmod is a no-op; the file is still protected
        # by the directory ACLs and the .gitignore.
        pass
    return key


@lru_cache
def get_fernet() -> Fernet:
    """Return a process-wide Fernet instance."""
    key = _load_or_create_master_key(MASTER_KEY_FILE)
    return Fernet(key)


def encrypt_str(plaintext: str) -> str:
    """Encrypt a string and return url-safe base64 ciphertext (utf-8 str).

    Empty / whitespace-only input short-circuits to "" — otherwise Fernet
    would still produce a valid (but non-empty) ciphertext for the empty
    string, which trips up `has_api_key` checks downstream.
    """
    if not plaintext or not plaintext.strip():
        return ""
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_str(token: str) -> str:
    """Decrypt a Fernet token back to plaintext.

    Raises InvalidToken if the key has changed or the ciphertext is corrupt.
    """
    if not token:
        return ""
    try:
        return get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt — the master key may have changed since this value was stored."
        ) from exc


def warn_if_unbacked() -> None:
    """Emit a one-time warning if no MASTER_KEY env var is set."""
    if not os.environ.get("MASTER_KEY"):
        warnings.warn(
            f"[crypto] No MASTER_KEY env var — using file {MASTER_KEY_FILE}. "
            "If you lose this file, encrypted DB secrets are unrecoverable.",
            stacklevel=2,
        )
