"""History listing & detail."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import execute, fetch, fetchrow
from app.schemas import HistoryDetail, HistoryItem, ModuleName

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/history", tags=["history"])


def _row_to_item(row, *, detail: bool = False) -> dict:
    d = dict(row)
    for k in ("params", "request_payload", "response_payload", "output_files"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except json.JSONDecodeError:
                d[k] = {} if k != "output_files" else []
        elif v is None:
            d[k] = {} if k != "output_files" else []
    if not isinstance(d.get("output_files"), list):
        d["output_files"] = []
    return d


@router.get("", response_model=list[HistoryItem])
async def list_history(
    module: Optional[ModuleName] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[HistoryItem]:
    if module:
        rows = await fetch(
            "SELECT * FROM generation_history WHERE module = $1 ORDER BY id DESC LIMIT $2 OFFSET $3",
            module, limit, offset,
        )
    else:
        rows = await fetch(
            "SELECT * FROM generation_history ORDER BY id DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
    return [HistoryItem(**_row_to_item(r)) for r in rows]


@router.get("/{history_id}", response_model=HistoryDetail)
async def get_history(history_id: int) -> HistoryDetail:
    row = await fetchrow("SELECT * FROM generation_history WHERE id = $1", history_id)
    if not row:
        raise HTTPException(404, "Not found")
    return HistoryDetail(**_row_to_item(row, detail=True))


@router.delete("/{history_id}")
async def delete_history(history_id: int) -> dict:
    res = await execute("DELETE FROM generation_history WHERE id = $1", history_id)
    return {"ok": res.endswith(" 1")}
