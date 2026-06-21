"""CRUD for key_providers.

API keys live here, decoupled from per-module configs. A `key_provider` is
just a named, encrypted blob with an enabled flag. The configs router
references these via `key_provider_id`.
"""

from __future__ import annotations

import json
import logging
import time

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.crypto import decrypt_str, encrypt_str
from app.database import execute, fetch, fetchrow
from app.schemas import (
    KeyProviderCreate,
    KeyProviderOut,
    KeyProviderTestResult,
    KeyProviderUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/key-providers", tags=["key-providers"])


def _row_to_out(row) -> dict[str, Any]:
    d = dict(row)
    d["has_api_key"] = bool(d.pop("api_key_encrypted"))
    return d


@router.get("", response_model=list[KeyProviderOut])
async def list_providers() -> list[KeyProviderOut]:
    rows = await fetch("SELECT * FROM key_providers ORDER BY id ASC")
    return [KeyProviderOut(**_row_to_out(r)) for r in rows]


@router.get("/{provider_id}", response_model=KeyProviderOut)
async def get_provider(provider_id: int) -> KeyProviderOut:
    row = await fetchrow("SELECT * FROM key_providers WHERE id = $1", provider_id)
    if not row:
        raise HTTPException(404, "Key provider not found")
    return KeyProviderOut(**_row_to_out(row))


@router.post("", response_model=KeyProviderOut, status_code=201)
async def create_provider(body: KeyProviderCreate) -> KeyProviderOut:
    try:
        row = await fetchrow(
            """
            INSERT INTO key_providers (name, description, api_key_encrypted, enabled)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            body.name,
            body.description,
            encrypt_str(body.api_key),
            body.enabled,
        )
    except Exception as exc:
        msg = str(exc)
        if "unique" in msg.lower():
            raise HTTPException(409, f"A key provider named '{body.name}' already exists")
        raise HTTPException(400, msg)
    return KeyProviderOut(**_row_to_out(row))


@router.put("/{provider_id}", response_model=KeyProviderOut)
async def update_provider(provider_id: int, body: KeyProviderUpdate) -> KeyProviderOut:
    existing = await fetchrow("SELECT * FROM key_providers WHERE id = $1", provider_id)
    if not existing:
        raise HTTPException(404, "Key provider not found")

    fields: dict[str, Any] = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.description is not None:
        fields["description"] = body.description
    if "api_key" in body.model_fields_set:
        # Empty string explicitly clears the key.
        fields["api_key_encrypted"] = encrypt_str(body.api_key) if body.api_key else ""
    if body.enabled is not None:
        fields["enabled"] = body.enabled

    if not fields:
        return KeyProviderOut(**_row_to_out(existing))

    placeholders: list[str] = []
    real_args: list[Any] = [provider_id]
    idx = 2
    for k, v in fields.items():
        placeholders.append(f"{k} = ${idx}")
        real_args.append(v)
        idx += 1
    set_sql = ", ".join(placeholders) + ", updated_at = NOW()"

    try:
        row = await fetchrow(
            f"UPDATE key_providers SET {set_sql} WHERE id = $1 RETURNING *",
            *real_args,
        )
    except Exception as exc:
        msg = str(exc)
        if "unique" in msg.lower():
            raise HTTPException(409, "Name already used by another provider")
        raise HTTPException(400, msg)
    return KeyProviderOut(**_row_to_out(row))


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int) -> dict:
    # ON DELETE RESTRICT will surface a FK violation as a regular exception
    # here; translate it to a friendlier 409.
    try:
        res = await execute("DELETE FROM key_providers WHERE id = $1", provider_id)
    except Exception as exc:
        msg = str(exc).lower()
        if "foreign key" in msg or "violates" in msg or "referenced" in msg:
            raise HTTPException(
                409,
                "This provider is in use by one or more configs. "
                "Reassign or remove those configs first.",
            )
        raise HTTPException(400, str(exc))
    return {"ok": res.endswith(" 1")}


@router.post("/{provider_id}/test", response_model=KeyProviderTestResult)
async def test_provider(provider_id: int) -> KeyProviderTestResult:
    """Send a minimal "ping" to the first enabled api_config to verify the
    key works end-to-end. Falls back to a dry /v1/chat/completions probe if
    no configs exist yet — that endpoint exists on the MiniMax platform and
    accepts the same Bearer auth, so it's a cheap reachability check."""
    row = await fetchrow(
        "SELECT api_key_encrypted FROM key_providers WHERE id = $1", provider_id
    )
    if not row:
        raise HTTPException(404, "Key provider not found")
    api_key_enc = row["api_key_encrypted"]
    if not api_key_enc:
        return {"ok": False, "message": "API key is empty"}

    api_key = decrypt_str(api_key_enc)
    if not api_key:
        return {"ok": False, "message": "API key is empty"}

    settings = get_settings()
    timeout = httpx.Timeout(settings.request_timeout, connect=30.0)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # /v1/models is the cheapest end-to-end auth check on the MiniMax
            # platform — it accepts the same Bearer key, returns 200 with the
            # model list when valid, 401 when the key is rejected, and never
            # burns quota.
            resp = await client.get(
                "https://api.minimaxi.com/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "message": f"Network error: {exc}",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    latency_ms = int((time.perf_counter() - started) * 1000)
    snippet: Any
    try:
        snippet = resp.json()
        if isinstance(snippet, (dict, list)):
            snippet = json.dumps(snippet)[:500]
    except Exception:
        snippet = resp.text[:500]

    if resp.status_code in (200, 201, 204):
        return {
            "ok": True,
            "message": f"HTTP {resp.status_code}: auth accepted.",
            "latency_ms": latency_ms,
            "http_status": resp.status_code,
            "sample_response": snippet,
        }
    return {
        "ok": False,
        "message": f"HTTP {resp.status_code}: {resp.text[:300]}",
        "latency_ms": latency_ms,
        "http_status": resp.status_code,
        "sample_response": snippet,
    }
