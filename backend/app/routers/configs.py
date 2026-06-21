"""CRUD for api_configs.

Configs reference a key_providers row via key_provider_id; the key itself
lives on the provider. See app/routers/key_providers.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

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


# Columns we join in for the response shape. Has to stay in sync with the
# SELECT below.
#
# `n_keyed_enabled` is the count of key_providers rows that are enabled
# AND have a non-empty api_key_encrypted. We use it to compute
# `has_api_key` correctly for configs whose `key_provider_id` is NULL
# — those rely on the runtime's auto-bind path. Without this subquery
# the field would only reflect the explicitly-bound provider and the
# UI would show "no key" even when a request would actually succeed.
_BASE_SELECT = """
    SELECT
        c.*,
        kp.id           AS kp_id,
        kp.name         AS kp_name,
        kp.api_key_encrypted AS kp_api_key_encrypted,
        (
            SELECT COUNT(*) FROM key_providers kp2
            WHERE kp2.enabled = TRUE AND kp2.api_key_encrypted <> ''
        ) AS n_keyed_enabled
    FROM api_configs c
    LEFT JOIN key_providers kp ON kp.id = c.key_provider_id
"""


def _resolve_has_api_key(d: dict[str, Any]) -> bool:
    """Compute the effective has_api_key for a config row, considering
    both the explicit binding AND the auto-bind path:

      * Explicit binding (key_provider_id set):
          True iff that provider's row has a non-empty key.
      * No binding (key_provider_id IS NULL):
          * exactly 1 keyed-enabled provider → auto-bind resolves it → True
          * 0 keyed-enabled providers       → nothing to bind to      → False
          * 2+ keyed-enabled providers      → ambiguous (load_config
                                              raises at runtime)        → False
    """
    if d.get("kp_id") is not None:
        return bool(d.get("kp_api_key_encrypted"))
    # Unbound — depend on auto-bind resolvability.
    return d.get("n_keyed_enabled", 0) == 1


def _row_to_out(row) -> dict[str, Any]:
    d = dict(row)
    # Bring the joined provider columns out under stable names.
    d["key_provider_id"] = d.pop("kp_id", None)
    d["key_provider_name"] = d.pop("kp_name", None)
    kp_key = d.pop("kp_api_key_encrypted", None)
    d["has_api_key"] = _resolve_has_api_key(d)
    # The kp_key local was only used inside _resolve_has_api_key; drop it
    # so it doesn't leak into the JSON response.
    _ = kp_key
    # Drop the legacy column from the response — even if it's still on the
    # table (we keep it for migration safety), the API contract no longer
    # exposes it.
    d.pop("api_key_encrypted", None)
    d.pop("n_keyed_enabled", None)
    # asyncpg returns dict / list for jsonb; the legacy column path may
    # still hand us strings if the row was double-encoded.
    for k in ("request_template", "response_parser", "default_params"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except json.JSONDecodeError:
                d[k] = {}
    return d


async def _resolve_provider_id(
    requested: Optional[int],
) -> Optional[int]:
    """Apply the auto-bind rule: when the caller leaves key_provider_id
    blank AND there's exactly one enabled provider, use it; otherwise
    honour the explicit value (or leave NULL)."""
    if requested is not None:
        row = await fetchrow(
            "SELECT id FROM key_providers WHERE id = $1", requested
        )
        if not row:
            raise HTTPException(400, f"key_provider_id={requested} does not exist")
        return requested
    row = await fetchrow(
        "SELECT COUNT(*) AS n FROM key_providers WHERE enabled = TRUE"
    )
    n = (row or {}).get("n", 0) or 0
    if n == 1:
        only = await fetchrow(
            "SELECT id FROM key_providers WHERE enabled = TRUE ORDER BY id ASC LIMIT 1"
        )
        return only["id"] if only else None
    return None


@router.get("", response_model=list[ConfigOut])
async def list_configs() -> list[ConfigOut]:
    rows = await fetch(_BASE_SELECT + " ORDER BY c.id ASC")
    return [ConfigOut(**_row_to_out(r)) for r in rows]


@router.get("/{module}", response_model=ConfigOut)
async def get_config(module: ModuleName) -> ConfigOut:
    row = await fetchrow(
        _BASE_SELECT + " WHERE c.module = $1 ORDER BY c.id ASC LIMIT 1", module
    )
    if not row:
        raise HTTPException(404, f"No config for module={module}")
    return ConfigOut(**_row_to_out(row))


@router.post("", response_model=ConfigOut, status_code=201)
async def create_config(body: ConfigCreate) -> ConfigOut:
    provider_id = await _resolve_provider_id(body.key_provider_id)
    try:
        row = await fetchrow(
            """
            INSERT INTO api_configs
              (module, display_name, key_provider_id, base_url, endpoint_path, model,
               request_template, response_parser, default_params, enabled)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10)
            RETURNING *
            """,
            body.module,
            body.display_name,
            provider_id,
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
    # Re-read with the join so key_provider_name / has_api_key come back filled.
    full = await fetchrow(_BASE_SELECT + " WHERE c.id = $1", row["id"])
    return ConfigOut(**_row_to_out(full))


@router.put("/{config_id}", response_model=ConfigOut)
async def update_config(config_id: int, body: ConfigUpdate) -> ConfigOut:
    existing = await fetchrow("SELECT * FROM api_configs WHERE id = $1", config_id)
    if not existing:
        raise HTTPException(404, "Config not found")

    fields: dict[str, Any] = {}
    if body.display_name is not None:
        fields["display_name"] = body.display_name
    if "key_provider_id" in body.model_fields_set:
        # Honour the explicit assignment VERBATIM. This is the update path
        # — auto-bind semantics (where a `null` falls back to the single
        # enabled provider) belong on the *create* path, not here. An
        # explicit `null` from the client means "unbind", full stop.
        fields["key_provider_id"] = body.key_provider_id
        if fields["key_provider_id"] is not None:
            row = await fetchrow(
                "SELECT id FROM key_providers WHERE id = $1",
                fields["key_provider_id"],
            )
            if not row:
                raise HTTPException(
                    400, f"key_provider_id={fields['key_provider_id']} does not exist"
                )
        # If the client sent `null` and the row already has a non-null
        # key_provider_id, fields["key_provider_id"] is now None, which
        # the SET clause below will write as SQL NULL.
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
        full = await fetchrow(_BASE_SELECT + " WHERE c.id = $1", config_id)
        return ConfigOut(**_row_to_out(full))

    # Build dynamic SET clause with type-aware placeholders.
    JSONB_FIELDS = {"request_template", "response_parser", "default_params"}
    placeholders: list[str] = []
    real_args: list[Any] = [config_id]
    idx = 2
    for k, v in fields.items():
        if k in JSONB_FIELDS:
            placeholders.append(f"{k} = ${idx}::jsonb")
        else:
            placeholders.append(f"{k} = ${idx}")
        real_args.append(v)
        idx += 1
    set_sql = ", ".join(placeholders) + ", updated_at = NOW()"

    await execute(
        f"UPDATE api_configs SET {set_sql} WHERE id = $1",
        *real_args,
    )
    full = await fetchrow(_BASE_SELECT + " WHERE c.id = $1", config_id)
    return ConfigOut(**_row_to_out(full))


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
