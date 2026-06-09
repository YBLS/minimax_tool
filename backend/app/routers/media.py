"""Serve files saved under ./uploads/ (read-only)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.utils.files import abs_from_url_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{path:path}")
async def get_media(path: str):
    abs_path: Path | None = abs_from_url_path(f"api/media/{path}")
    if abs_path is None or not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(abs_path)
