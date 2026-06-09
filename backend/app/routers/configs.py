"""CRUD for api_configs."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.crypto import encrypt_str
from app.database import execute, fetch, fetchrow
from app.schemas import (
    ConfigCreate,
    ConfigOut,
    ConfigTestResult,
    ConfigUpdate,
    ModuleName,
)
from app.services.generator import test_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/configs", tags=["configs"])


def _row_to_out(row) -> dict[str, Any]:
    d = dict(row)
    d["has_api_key"] = bool(d.pop("api_key_encrypted"))
    # asyncpg returns dict / list for jsonb
    for k in ("request_template", "response_parser", "default_params"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except json.JSONDecodeError:
                d[k] = {}
    return d


@router.get("", response_model=list[ConfigOut])
async def list_configs() -> list[ConfigOut]:
    rows = await fetch("SELECT * FROM api_configs ORDER BY id ASC")
    return [ConfigOut(**_row_to_out(r)) for r in rows]


@router.get("/{module}", response_model=ConfigOut)
async def get_config(module: ModuleName) -> ConfigOut:
    row = await fetchrow(
        "SELECT * FROM api_configs WHERE module = $1 ORDER BY id ASC LIMIT 1", module
    )
    if not row:
        raise HTTPException(404, f"No config for module={module}")
    return ConfigOut(**_row_to_out(row))


@router.post("", response_model=ConfigOut, status_code=201)
async def create_config(body: ConfigCreate) -> ConfigOut:
    try:
        row = await fetchrow(
            """
            INSERT INTO api_configs
              (module, display_name, api_key_encrypted, base_url, endpoint_path, model,
               request_template, response_parser, default_params, enabled)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10)
            RETURNING *
            """,
            body.module,
            body.display_name,
            encrypt_str(body.api_key),
            body.base_url,
            body.endpoint_path,
            body.model,
            json.dumps(body.request_template, ensure_ascii=False),
            json.dumps(body.response_parser, ensure_ascii=False),
            json.dumps(body.default_params, ensure_ascii=False),
            body.enabled,
        )
    except Exception as exc:  # likely unique violation
        msg = str(exc)
        if "unique" in msg.lower():
            raise HTTPException(409, f"Module '{body.module}' already has a config")
        raise HTTPException(400, msg)
    return ConfigOut(**_row_to_out(row))


@router.put("/{config_id}", response_model=ConfigOut)
async def update_config(config_id: int, body: ConfigUpdate) -> ConfigOut:
    existing = await fetchrow("SELECT * FROM api_configs WHERE id = $1", config_id)
    if not existing:
        raise HTTPException(404, "Config not found")

    fields: dict[str, Any] = {}
    if body.display_name is not None:
        fields["display_name"] = body.display_name
    if body.api_key is not None:
        # Empty string explicitly clears the key
        fields["api_key_encrypted"] = encrypt_str(body.api_key) if body.api_key else ""
    if body.base_url is not None:
        fields["base_url"] = body.base_url
    if body.endpoint_path is not None:
        fields["endpoint_path"] = body.endpoint_path
    if body.model is not None:
        fields["model"] = body.model
    if body.request_template is not None:
        fields["request_template"] = json.dumps(body.request_template, ensure_ascii=False)
    if body.response_parser is not None:
        fields["response_parser"] = json.dumps(body.response_parser, ensure_ascii=False)
    if body.default_params is not None:
        fields["default_params"] = json.dumps(body.default_params, ensure_ascii=False)
    if body.enabled is not None:
        fields["enabled"] = body.enabled

    if not fields:
        return ConfigOut(**_row_to_out(existing))

    # Build dynamic SET clause
    set_sql = ", ".join(f"{k} = ${i+2}::jsonb" if k in {"request_template", "response_parser", "default_params"}
                        else f"{k} = ${i+2}" for i, k in enumerate(fields))
    set_sql = set_sql.replace("::jsonb::jsonb", "::jsonb")
    args = [config_id, *fields.values()]
    # If there is no JSONB field, the cast above would not match; we rebuild safely:
    placeholders: list[str] = []
    real_args: list[Any] = [config_id]
    idx = 2
    for k, v in fields.items():
        if k in {"request_template", "response_parser", "default_params"}:
            placeholders.append(f"{k} = ${idx}::jsonb")
        else:
            placeholders.append(f"{k} = ${idx}")
        real_args.append(v)
        idx += 1
    set_sql = ", ".join(placeholders) + ", updated_at = NOW()"

    row = await fetchrow(
        f"UPDATE api_configs SET {set_sql} WHERE id = $1 RETURNING *",
        *real_args,
    )
    return ConfigOut(**_row_to_out(row))


@router.delete("/{config_id}")
async def delete_config(config_id: int) -> dict:
    res = await execute("DELETE FROM api_configs WHERE id = $1", config_id)
    # asyncpg returns "DELETE n"
    return {"ok": res.endswith(" 1")}


@router.post("/{config_id}/test", response_model=ConfigTestResult)
async def test_config_route(config_id: int) -> ConfigTestResult:
    row = await fetchrow("SELECT module FROM api_configs WHERE id = $1", config_id)
    if not row:
        raise HTTPException(404, "Config not found")
    res = await test_config(row["module"], config_id)
    return ConfigTestResult(**res)
