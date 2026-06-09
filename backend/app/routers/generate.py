"""Trigger generation and return persisted files."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.database import execute, fetchrow
from app.schemas import GenerateRequest, GenerateResult, ModuleName
from app.services.generator import GenerationError, run_generation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generate"])


@router.post("/{module}", response_model=GenerateResult)
async def generate(module: str, body: GenerateRequest) -> GenerateResult:
    if not body.prompt.strip():
        raise HTTPException(400, "prompt cannot be empty")

    # Insert pending row
    row = await fetchrow(
        """
        INSERT INTO generation_history (module, config_id, prompt, params, status)
        VALUES ($1, $2, $3, $4::jsonb, 'running')
        RETURNING id, created_at
        """,
        module,
        body.config_id,
        body.prompt,
        _json(body.params),
    )
    history_id = row["id"]

    try:
        files, request_payload, response_payload, duration_ms = await run_generation(
            module=module, prompt=body.prompt, params=body.params, config_id=body.config_id
        )
    except GenerationError as exc:
        await execute(
            """
            UPDATE generation_history
               SET status = 'failed', error_message = $2, duration_ms = $3,
                   request_payload = $4::jsonb
             WHERE id = $1
            """,
            history_id,
            str(exc)[:2000],
            0,
            _json({"error": str(exc), "module": module, "prompt": body.prompt, "params": body.params}),
        )
        raise HTTPException(502, f"Upstream error: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate failed")
        await execute(
            """
            UPDATE generation_history
               SET status = 'failed', error_message = $2
             WHERE id = $1
            """,
            history_id,
            f"{type(exc).__name__}: {exc}"[:2000],
        )
        raise HTTPException(500, f"{type(exc).__name__}: {exc}")

    output_files_json = [f.model_dump() for f in files]
    await execute(
        """
        UPDATE generation_history
           SET status = 'success', output_files = $2::jsonb, request_payload = $3::jsonb,
               response_payload = $4::jsonb, duration_ms = $5
         WHERE id = $1
        """,
        history_id,
        _json(output_files_json),
        _json(request_payload),
        _json(response_payload),
        duration_ms,
    )

    final = await fetchrow(
        "SELECT * FROM generation_history WHERE id = $1", history_id
    )
    return _row_to_result(final)


def _json(d: dict) -> str:
    import json
    return json.dumps(d, ensure_ascii=False)


def _row_to_result(row) -> GenerateResult:
    d = dict(row)
    import json
    for k in ("params", "request_payload", "response_payload", "output_files"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except json.JSONDecodeError:
                d[k] = {}
        elif v is None:
            d[k] = {} if k != "output_files" else []
    if not isinstance(d.get("output_files"), list):
        d["output_files"] = []
    return GenerateResult(**d)
