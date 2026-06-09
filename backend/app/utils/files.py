"""File storage utilities — write generated media to ./uploads/ and serve via /api/media."""

from __future__ import annotations

import hashlib
import mimetypes
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

# Map response-format / file types to extensions + mime
_MIME_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
    "audio/aac": "aac",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
}

_EXT_TO_TYPE = {
    "image": {"png", "jpg", "jpeg", "webp", "gif"},
    "audio": {"mp3", "wav", "ogg", "flac", "aac"},
    "video": {"mp4", "mov", "webm"},
}


def file_kind(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    for kind, exts in _EXT_TO_TYPE.items():
        if ext in exts:
            return kind
    return "binary"


def ext_from_content_type(content_type: str) -> str:
    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type in _MIME_TO_EXT:
        return _MIME_TO_EXT[content_type]
    # Fallback: guess from content_type / "octet-stream"
    ext = mimetypes.guess_extension(content_type) or ""
    return ext.lstrip(".") or "bin"


def ext_from_url(url: str, default: str = "bin") -> str:
    # Strip query string
    path = url.split("?")[0].split("#")[0]
    if "." in path.rsplit("/", 1)[-1]:
        ext = path.rsplit(".", 1)[-1].lower()
        if 2 <= len(ext) <= 5 and ext.isalnum():
            return ext
    return default


def _safe_filename(prompt: str) -> str:
    """Return a short, filesystem-safe hint derived from the prompt."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", prompt.strip())[:32]
    return cleaned.strip("-") or "gen"


def build_path(
    *,
    module: str,
    ext: str,
    subdir: Optional[str] = None,
    hint: str = "",
) -> Path:
    """Build a unique destination path under uploads/."""
    settings = get_settings()
    now = datetime.now()
    parts = [module, now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")]
    if subdir:
        parts.append(subdir)
    base = settings.upload_dir.joinpath(*parts)
    base.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%H%M%S")
    uid = uuid.uuid4().hex[:8]
    name = f"{ts}_{uid}_{hint}" if hint else f"{ts}_{uid}"
    return base / f"{name}.{ext.lstrip('.')}"


async def download_to_disk(
    url: str, dest: Path, *, timeout: float = 180.0
) -> tuple[Path, int, str]:
    """Stream `url` to `dest`. Returns (dest, size, content_type)."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "application/octet-stream")
            size = 0
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    fh.write(chunk)
                    size += len(chunk)
    return dest, size, content_type


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def media_url(absolute_path: Path) -> str:
    """Convert an absolute path under uploads/ to a public URL."""
    settings = get_settings()
    rel = absolute_path.resolve().relative_to(settings.upload_dir.resolve())
    return f"/api/media/{rel.as_posix()}"


def abs_from_url_path(url_path: str) -> Optional[Path]:
    """Reverse of media_url(). Returns None if path escapes uploads/."""
    settings = get_settings()
    rel = url_path.lstrip("/")
    if rel.startswith("api/media/"):
        rel = rel[len("api/media/"):]
    candidate = (settings.upload_dir / rel).resolve()
    base = settings.upload_dir.resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate
