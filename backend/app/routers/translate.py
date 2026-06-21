"""Translate router — thin wrapper around app.services.translate."""

from __future__ import annotations

import logging
import json
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.translate import (
    LANGUAGE_NAMES,
    TranslationError,
    run_translation,
)
from app.database import execute, fetchrow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/translate", tags=["translate"])


class TranslateRequestBody(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    source: str = Field(default="auto")
    target: str
    config_id: Optional[int] = None
    # Per-call model override. When omitted, the config row's `model` is
    # used (so a single shared config can serve several models just by
    # changing the dropdown in the UI). Empty string also falls back.
    model: Optional[str] = Field(default=None, max_length=200)


class TranslateResponseBody(BaseModel):
    translated_text: str
    source: str
    target: str
    model: str
    duration_ms: int
    detected_source: Optional[str] = None


@router.get("/languages")
async def list_languages() -> dict:
    """Return the language catalogue the UI uses for source/target pickers."""
    return {
        "languages": [
            {"code": code, "name": name}
            for code, name in LANGUAGE_NAMES.items()
        ],
    }


@router.post("", response_model=TranslateResponseBody)
async def translate(body: TranslateRequestBody) -> TranslateResponseBody:
    params = {
        "source": body.source,
        "target": body.target,
        "model": body.model,
    }
    row = await fetchrow(
        """
        INSERT INTO generation_history (module, config_id, prompt, params, status)
        VALUES ('translate', $1, $2, $3::jsonb, 'running')
        RETURNING id
        """,
        body.config_id,
        body.text,
        json.dumps(params, ensure_ascii=False),
    )
    history_id = row["id"]
    started = time.perf_counter()
    try:
        r = await run_translation(
            text=body.text,
            source=body.source,
            target=body.target,
            config_id=body.config_id,
            model=body.model,
        )
    except TranslationError as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await execute(
            """
            UPDATE generation_history
               SET status='failed', error_message=$2, duration_ms=$3,
                   request_payload=$4::jsonb
             WHERE id=$1
            """,
            history_id,
            str(exc)[:2000],
            duration_ms,
            json.dumps(params, ensure_ascii=False),
        )
        # 4xx for user input problems, 502 for upstream failures, 500 for the rest.
        status = 502 if exc.http_status else 400
        raise HTTPException(status, str(exc))
    await execute(
        """
        UPDATE generation_history
           SET status='success', duration_ms=$2,
               request_payload=$3::jsonb, response_payload=$4::jsonb
         WHERE id=$1
        """,
        history_id,
        r.duration_ms,
        json.dumps(params, ensure_ascii=False),
        json.dumps(
            {
                "translated_text": r.translated_text,
                "detected_source": r.detected_source,
                "model": r.model,
            },
            ensure_ascii=False,
        ),
    )
    return TranslateResponseBody(
        translated_text=r.translated_text,
        source=r.source,
        target=r.target,
        model=r.model,
        duration_ms=r.duration_ms,
        detected_source=r.detected_source,
    )
