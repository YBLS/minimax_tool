"""SQL schema bootstrap.

Run once on first startup; idempotent (CREATE TABLE IF NOT EXISTS).
The init_db script does the same thing in a one-shot CLI for the user.
"""

from __future__ import annotations

import logging

from app.database import Database, execute

logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS api_configs (
    id                SERIAL PRIMARY KEY,
    module            VARCHAR(50)  UNIQUE NOT NULL,
    display_name      VARCHAR(100) NOT NULL,
    api_key_encrypted TEXT         NOT NULL DEFAULT '',
    base_url          VARCHAR(500) NOT NULL,
    endpoint_path     VARCHAR(500) NOT NULL,
    model             VARCHAR(200) NOT NULL DEFAULT '',
    request_template  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    response_parser   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    default_params    JSONB        NOT NULL DEFAULT '{}'::jsonb,
    enabled           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS generation_history (
    id               SERIAL PRIMARY KEY,
    module           VARCHAR(50)  NOT NULL,
    config_id        INTEGER      REFERENCES api_configs(id) ON DELETE SET NULL,
    prompt           TEXT         NOT NULL DEFAULT '',
    params           JSONB        NOT NULL DEFAULT '{}'::jsonb,
    request_payload  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    response_payload JSONB        NOT NULL DEFAULT '{}'::jsonb,
    output_files     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending',
    error_message    TEXT         NOT NULL DEFAULT '',
    duration_ms      INTEGER      NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_history_module_created
    ON generation_history(module, created_at DESC);

CREATE TABLE IF NOT EXISTS app_secrets (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) UNIQUE NOT NULL,
    value_encrypted TEXT         NOT NULL,
    description     TEXT         NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
"""


SEED_CONFIGS = [
    # Image — POST /v1/image_generation
    # Docs: https://platform.minimaxi.com/document/ImageGeneration
    # Response shape: { data: { image_urls: [...] }, metadata, base_resp }
    {
        "module": "image",
        "display_name": "Image · image-01",
        "base_url": "https://api.minimaxi.com",
        "endpoint_path": "/v1/image_generation",
        "model": "image-01",
        "request_template": {
            "method": "POST",
            "headers": {
                "Authorization": "Bearer {{api_key}}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": "{{model}}",
                "prompt": "{{prompt}}",
                "aspect_ratio": "{{aspect_ratio:s|1:1}}",
                "n": "{{n:i|1}}",
                "response_format": "{{response_format:s|url}}",
                "prompt_optimizer": "{{prompt_optimizer:b|false}}",
                "aigc_watermark": "{{aigc_watermark:b|false}}",
            },
        },
        "response_parser": {
            "type": "jsonpath",
            "items_path": "$.data.image_urls",
            "default_ext": "png",
        },
        "default_params": {
            "aspect_ratio": "1:1",
            "n": 1,
            "response_format": "url",
            "prompt_optimizer": False,
            "aigc_watermark": False,
        },
    },
    # Voice / TTS — POST /v1/t2a_v2 (binary response)
    # Docs: https://www.minimaxi.com/document/T2A%20V2
    # Current flagship: speech-2.6-turbo (speech-2.5-hd-preview is a preview,
    # speech-01-turbo was retired and returns empty body).
    {
        "module": "voice",
        "display_name": "Voice · speech-2.6-turbo",
        "base_url": "https://api.minimaxi.com",
        "endpoint_path": "/v1/t2a_v2",
        "model": "speech-2.6-turbo",
        "request_template": {
            "method": "POST",
            "headers": {
                "Authorization": "Bearer {{api_key}}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": "{{model}}",
                "text": "{{prompt}}",
                "voice_setting": {
                    "voice_id": "{{voice_id:s|female-shaonv}}",
                    "speed": "{{speed:n|1.0}}",
                    "vol": "{{vol:n|1.0}}",
                    "pitch": "{{pitch:i|0}}",
                },
                "audio_setting": {
                    "sample_rate": "{{sample_rate:i|32000}}",
                    "bitrate": "{{bitrate:i|128000}}",
                    "format": "{{format:s|mp3}}",
                    "channel": "{{channel:i|1}}",
                },
            },
        },
        "response_parser": {
            # /v1/t2a_v2 with speech-2.6+ returns JSON {"data":{"audio":"<hex>"}}
            # — same shape as /v1/music_generation, not a raw binary mp3.
            "type": "minimax_music",
            "items_path": "$.data",
            "default_ext": "mp3",
        },
        "default_params": {
            "voice_id": "female-shaonv",
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 0,
            "format": "mp3",
            "sample_rate": 32000,
            "bitrate": 128000,
            "channel": 1,
        },
    },
    # Music — POST /v1/music_generation
    # Response shape: { data: { audio: "<hex>" } }  OR with download URL depending on version
    # Current flagship: music-2.0 (music-1.5 was the previous generation;
    # music-01 is retired and returns 2013 "wrong params" error).
    {
        "module": "music",
        "display_name": "Music · music-2.0",
        "base_url": "https://api.minimaxi.com",
        "endpoint_path": "/v1/music_generation",
        "model": "music-2.0",
        "request_template": {
            "method": "POST",
            "headers": {
                "Authorization": "Bearer {{api_key}}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": "{{model}}",
                "prompt": "{{prompt}}",
                "lyrics": "{{lyrics:s|}}",
                "audio_setting": {
                    "sample_rate": "{{sample_rate:i|32000}}",
                    "bitrate": "{{bitrate:i|128000}}",
                    "format": "{{format:s|mp3}}",
                },
            },
        },
        "response_parser": {
            "type": "minimax_music",
            "items_path": "$.data",
            "default_ext": "mp3",
        },
        "default_params": {
            # music-2.0 requires lyrics (empty → base_resp 2013).
            # [Instrumental] marker tells the model to skip vocals.
            "lyrics": "[Instrumental]",
            "format": "mp3",
            "sample_rate": 32000,
            "bitrate": 128000,
        },
    },
    # Video — POST /v1/video_generation (async) + GET /v1/query/video_generation
    # Response shape: { task_id, base_resp } → poll → { status, file_id } → GET /v1/files/retrieve → { download_url }
    # Current flagship: MiniMax-Hailuo-02 (video-01 was retired and returns 404
    # — and yes, the submit request still consumes quota, so do not retry that name).
    #
    # Three sub-modes all POST to the same endpoint; they differ only in
    # required/optional body fields:
    #   • T2V   — text-only            → only `prompt` (in addition to model)
    #   • I2V   — image → video        → adds `first_frame_image` (URL or data: URL)
    #   • FL2V  — first+last frame     → adds `last_frame_image` (FL2V: Hailuo-02 only,
    #                                    no 512P, no fast_pretreatment)
    # All three accept the optional `duration`, `resolution`, `prompt_optimizer`,
    # `fast_pretreatment` (T2V+I2V only), `aigc_watermark`, `callback_url`.
    # Unset placeholders are stripped by _drop_unset, so any subset is safe.
    {
        "module": "video",
        "display_name": "Video · MiniMax-Hailuo-02",
        "base_url": "https://api.minimaxi.com",
        "endpoint_path": "/v1/video_generation",
        "model": "MiniMax-Hailuo-02",
        "request_template": {
            "method": "POST",
            "headers": {
                "Authorization": "Bearer {{api_key}}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": "{{model}}",
                "prompt": "{{prompt}}",
                "first_frame_image": "{{first_frame_image:s|}}",
                "last_frame_image": "{{last_frame_image:s|}}",
                "duration": "{{duration:i|6}}",
                "resolution": "{{resolution:s|768P}}",
                "prompt_optimizer": "{{prompt_optimizer:b|true}}",
                "fast_pretreatment": "{{fast_pretreatment:b|false}}",
                "aigc_watermark": "{{aigc_watermark:b|false}}",
                "callback_url": "{{callback_url:s|}}",
            },
        },
        "response_parser": {
            "type": "async_task",
            "task_id_path": "$.task_id",
            "query_method": "GET",
            "query_path": "/v1/query/video_generation",
            "query_params": {"task_id": "{{task_id}}"},
            "terminal_statuses": ["Success", "Finished", "Completed", "success", "finished", "completed"],
            "failed_statuses": ["Fail", "Failed", "failure"],
            "file_id_path": "$.file_id",
            "download_method": "GET",
            "download_path": "/v1/files/retrieve",
            "download_body": {"file_id": "{{file_id}}"},
            "download_url_path": "$.file.download_url",
            "default_ext": "mp4",
            "poll_interval": 5.0,
            "max_wait": 600.0,
        },
        "default_params": {
            "duration": 6,
            "resolution": "768P",
            "prompt_optimizer": True,
            "aigc_watermark": False,
        },
    },
]


async def init_schema() -> None:
    """Run schema bootstrap and seed default configs (no key)."""
    await Database.init()
    for stmt in SCHEMA_SQL.strip().split(";"):
        clean = stmt.strip()
        if clean:
            await execute(clean)

    # Seed default configs only if they don't exist yet (preserves user's edits / keys).
    from app.database import fetchrow  # local import to avoid cycle
    for cfg in SEED_CONFIGS:
        existing = await fetchrow(
            "SELECT id FROM api_configs WHERE module = $1", cfg["module"]
        )
        if existing:
            continue
        await execute(
            """
            INSERT INTO api_configs
              (module, display_name, base_url, endpoint_path, model,
               request_template, response_parser, default_params, enabled)
            VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb, TRUE)
            """,
            cfg["module"],
            cfg["display_name"],
            cfg["base_url"],
            cfg["endpoint_path"],
            cfg["model"],
            _json(cfg["request_template"]),
            _json(cfg["response_parser"]),
            _json(cfg["default_params"]),
        )
        logger.info("Seeded default config for module=%s", cfg["module"])


def _json(d: dict) -> str:
    import json
    return json.dumps(d, ensure_ascii=False)
