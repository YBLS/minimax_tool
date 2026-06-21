"""Liveness + DB connectivity check."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.database import fetchval

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict:
    try:
        v = await fetchval("SELECT 1")
        db_ok = v == 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("health: db check failed")
        return {"status": "degraded", "db": False, "error": str(exc)}
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "version": "0.2.0",
    }
