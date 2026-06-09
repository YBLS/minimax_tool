"""Generic encrypted secret store (for any extra API keys the user wants to manage)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.crypto import encrypt_str
from app.database import execute, fetch, fetchrow
from app.schemas import SecretMeta, SecretUpsert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


@router.get("", response_model=list[SecretMeta])
async def list_secrets() -> list[SecretMeta]:
    rows = await fetch("SELECT * FROM app_secrets ORDER BY name ASC")
    out: list[SecretMeta] = []
    for r in rows:
        d = dict(r)
        d["has_value"] = bool(d.pop("value_encrypted"))
        out.append(SecretMeta(**d))
    return out


@router.put("/{name}", status_code=200)
async def upsert_secret(name: str, body: SecretUpsert) -> dict:
    encrypted = encrypt_str(body.value)
    row = await fetchrow(
        "SELECT id FROM app_secrets WHERE name = $1", name
    )
    if row:
        await execute(
            "UPDATE app_secrets SET value_encrypted = $2, description = $3, updated_at = NOW() WHERE id = $1",
            row["id"], encrypted, body.description,
        )
    else:
        await execute(
            "INSERT INTO app_secrets (name, value_encrypted, description) VALUES ($1, $2, $3)",
            name, encrypted, body.description,
        )
    return {"ok": True}


@router.delete("/{name}")
async def delete_secret(name: str) -> dict:
    res = await execute("DELETE FROM app_secrets WHERE name = $1", name)
    return {"ok": res.endswith(" 1")}
