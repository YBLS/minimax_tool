"""SQL schema bootstrap.

Run once on first startup; idempotent (CREATE TABLE IF NOT EXISTS).
The init_db script does the same thing in a one-shot CLI for the user.

`key_providers` is the single home for API keys. `api_configs` no longer
stores the key itself; it just carries `key_provider_id` (nullable FK).
When a config has key_provider_id IS NULL and there's exactly one enabled
key provider, the generator / translator use it automatically.
"""

from __future__ import annotations

import logging
import json

from app.database import Database, execute, fetch, fetchrow
from app.security import redact_sensitive

logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS key_providers (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR(100) UNIQUE NOT NULL,
    description       TEXT         NOT NULL DEFAULT '',
    api_key_encrypted TEXT         NOT NULL DEFAULT '',
    enabled           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_configs (
    id                SERIAL PRIMARY KEY,
    module            VARCHAR(50)  UNIQUE NOT NULL,
    display_name      VARCHAR(100) NOT NULL,
    base_url          VARCHAR(500) NOT NULL,
    endpoint_path     VARCHAR(500) NOT NULL,
    model             VARCHAR(200) NOT NULL DEFAULT '',
    request_template  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    response_parser   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    default_params    JSONB        NOT NULL DEFAULT '{}'::jsonb,
    enabled           BOOLEAN      NOT NULL DEFAULT TRUE,
    -- legacy column, kept around so the migration in init_schema() can read
    -- existing keys out of it without an extra ALTER TABLE dance. New code
    -- must not write to it. The router rejects writes.
    api_key_encrypted TEXT         NOT NULL DEFAULT '',
    key_provider_id   INTEGER      REFERENCES key_providers(id) ON DELETE RESTRICT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
-- NB: the index on key_provider_id is created separately by
-- _ensure_api_configs_key_provider_column() so that legacy DBs (which
-- get the column added via ALTER TABLE) end up with both pieces in sync.

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
    # Translate — POST /v1/text/chatcompletion_v2.
    # v2 is the platform-recommended endpoint for M2.7 / M2.7-highspeed /
    # M3 and accepts the `thinking: {type: "disabled"}` knob that keeps
    # the model's reasoning out of the user-visible output. The older
    # `/v1/chat/completions` endpoint still works as a fallback (we drop
    # the thinking knob for it), but new installs default to v2.
    # The translator service in app/services/translate.py talks to this endpoint
    # directly (it does NOT reuse the request_template / response_parser engine —
    # chat completions is a different shape from the per-module media APIs).
    # We still seed a row here so the user can manage the API key in one place
    # (Config Center → Translate) and so the translate service has somewhere
    # to read base_url / model / api_key from.
    {
        "module": "translate",
        "display_name": "Translate · MiniMax-M2",
        "base_url": "https://api.minimaxi.com",
        "endpoint_path": "/v1/text/chatcompletion_v2",
        "model": "MiniMax-M2",
        # Placeholder — not used by the translate service, but required because
        # the column is NOT NULL. Keep it shaped like a valid chat-completions body
        # so the "Advanced" JSON editor in the UI is happy.
        "request_template": {
            "method": "POST",
            "headers": {
                "Authorization": "Bearer {{api_key}}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": "{{model}}",
                "messages": [
                    {"role": "system", "content": "You are a translator."},
                    {"role": "user", "content": "{{prompt}}"},
                ],
                "temperature": 0.3,
            },
        },
        "response_parser": {
            "type": "jsonpath",
            "items_path": "$.choices[0].message.content",
        },
        "default_params": {"temperature": 0.3},
    },
]


async def init_schema() -> None:
    """Run schema bootstrap, migrate legacy keys into key_providers, and seed
    default configs (no key)."""
    await Database.init()
    for stmt in SCHEMA_SQL.strip().split(";"):
        clean = stmt.strip()
        if clean:
            await execute(clean)

    # Idempotent column-add: an older api_configs table won't have
    # `key_provider_id` (it pre-dates the key_providers refactor). We add it
    # if missing. CREATE TABLE IF NOT EXISTS above is a no-op for an
    # existing table, so we have to patch in the new column separately.
    await _ensure_api_configs_key_provider_column()

    # Idempotent migration: if api_configs still has rows with
    # api_key_encrypted populated and no key_providers exist, lift those
    # keys into key_providers and link the rows. Runs once per fresh DB;
    # re-runs are no-ops because we check that no key_providers exist yet.
    await _migrate_legacy_keys()

    # One-time bridge for the old Secrets page: any app_secrets row
    # with a saved value gets promoted into a key_provider (one per
    # name), so users who put their module key in Secrets before the
    # refactor don't have to retype it. Re-runs are no-ops when the
    # same name already exists in key_providers.
    await _migrate_legacy_secrets()

    # Point the translate config at the v2 chat-completions endpoint
    # (the M2.7+ recommended path that supports `thinking: {type:
    # "disabled"}`). Older installs have `/v1/chat/completions`; flip
    # them in place. Idempotent — re-running on the v2 path is a no-op.
    await _ensure_translate_uses_v2_endpoint()
    await _redact_history_credentials()

    # Seed default configs only if they don't exist yet (preserves user's edits / keys).
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


async def _redact_history_credentials() -> None:
    """One-way cleanup for histories written by versions before 0.2.0."""
    rows = await fetch("SELECT id, request_payload FROM generation_history")
    cleaned = 0
    for row in rows:
        payload = row["request_payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                continue
        safe = redact_sensitive(payload)
        if safe != payload:
            await execute(
                "UPDATE generation_history SET request_payload=$2::jsonb WHERE id=$1",
                row["id"], json.dumps(safe, ensure_ascii=False),
            )
            cleaned += 1
    if cleaned:
        logger.warning("Redacted credentials from %d history row(s)", cleaned)


async def _ensure_api_configs_key_provider_column() -> None:
    """Add `key_provider_id` to api_configs if it doesn't exist yet.

    The fresh-install path goes through `CREATE TABLE IF NOT EXISTS` which
    already has the column; this is the bridge for DBs that were created
    before the key_providers refactor. Safe to re-run: ADD COLUMN with
    IF NOT EXISTS is a no-op when the column is already present.
    """
    await execute(
        "ALTER TABLE api_configs "
        "ADD COLUMN IF NOT EXISTS key_provider_id INTEGER "
        "REFERENCES key_providers(id) ON DELETE RESTRICT"
    )
    await execute(
        "CREATE INDEX IF NOT EXISTS idx_api_configs_provider "
        "ON api_configs(key_provider_id)"
    )


async def _ensure_translate_uses_v2_endpoint() -> None:
    """Flip the seeded translate config's endpoint_path from the legacy
    OpenAI-compatible `/v1/chat/completions` to the v2
    `/v1/text/chatcompletion_v2` recommended for M2.7 / M2.7-highspeed /
    M3.

    The v2 endpoint accepts the `thinking: {type: "disabled"}` knob
    that suppresses the model's reasoning from leaking into the
    user-visible `content` field. The legacy endpoint doesn't know
    about it, so leaving the older path would force us to either drop
    the knob (model still emits `<think>…</think>`) or clean the
    output post-hoc (regex stripping) — both worse than just using
    the right endpoint.

    Only the *seeded* `module = 'translate'` config is touched — the
    user can still pin a different endpoint for any module from the
    Config Center UI, and we don't want to fight them. Idempotent:
    the WHERE clause matches only the legacy path.
    """
    res = await execute(
        "UPDATE api_configs "
        "SET endpoint_path = '/v1/text/chatcompletion_v2' "
        "WHERE module = 'translate' "
        "  AND endpoint_path = '/v1/chat/completions'"
    )
    # `execute` returns "UPDATE n" — log it for visibility.
    if res and res.split()[-1] != "0":
        logger.info("Translate endpoint migrated to v2 (%s).", res)


async def _migrate_legacy_keys() -> None:
    """Promote any api_configs.api_key_encrypted values into key_providers,
    then clear them. This is the one-time bridge between the pre-key-provider
    schema and the new one — once the column is empty, subsequent runs are
    a no-op.

    Behaviour:
      * If no key_providers exist yet AND at least one api_configs row has a
        non-empty api_key_encrypted, create one key_providers row per distinct
        key. (In practice, all five modules share the same MiniMax key, so
        this collapses to a single "default (migrated)" provider — but the
        code handles the heterogeneous case too.)
      * Link every api_configs row with a non-empty legacy key to the matching
        provider.
      * Clear the legacy column on those rows so the next migration is a no-op.
    """
    # Bail out fast if there's nothing to migrate.
    legacy_rows = await fetch(
        "SELECT id, api_key_encrypted FROM api_configs "
        "WHERE api_key_encrypted <> '' ORDER BY id ASC"
    )
    if not legacy_rows:
        return

    # If the user already created a key_providers row manually, don't fight
    # them — leave legacy keys in place (they'll be ignored by new code) and
    # log a one-liner. They can manually clear via the API later.
    existing_providers = await fetchrow("SELECT COUNT(*) AS n FROM key_providers")
    if existing_providers and existing_providers["n"] > 0:
        logger.info(
            "Skipping legacy-key migration: %d key_providers already exist. "
            "Legacy api_key_encrypted values will be left in place (read by no one).",
            existing_providers["n"],
        )
        return

    # Distinct keys, in first-seen order.
    seen: dict[str, int] = {}  # key -> provider_id
    for row in legacy_rows:
        k = row["api_key_encrypted"]
        if k in seen:
            continue
        new_id = await fetchrow(
            """
            INSERT INTO key_providers (name, description, api_key_encrypted, enabled)
            VALUES ($1, $2, $3, TRUE)
            RETURNING id
            """,
            f"migrated-{row['id']}",
            "Auto-migrated from api_configs.api_key_encrypted (legacy schema). "
            "You can rename or delete this provider once you've verified everything still works.",
            k,
        )
        seen[k] = new_id["id"]
        logger.info("Migrated legacy key into key_providers id=%s", new_id["id"])

    # Link rows to their provider.
    for row in legacy_rows:
        provider_id = seen[row["api_key_encrypted"]]
        await execute(
            "UPDATE api_configs SET key_provider_id = $1 WHERE id = $2",
            provider_id,
            row["id"],
        )

    # Clear the legacy column. We keep the column itself (no DROP COLUMN) so
    # the migration is reversible and the schema diff stays boring.
    await execute("UPDATE api_configs SET api_key_encrypted = '' WHERE api_key_encrypted <> ''")
    logger.info(
        "Legacy api_key_encrypted values cleared. %d rows linked to %d provider(s).",
        len(legacy_rows),
        len(seen),
    )


async def _migrate_legacy_secrets() -> None:
    """Promote `app_secrets` rows with a saved value into `key_providers`.

    Background: the old Secrets page was a free-form key/value store
    (`app_secrets`). When the key_providers refactor landed, the two
    systems became independent and the user naturally expected "I set
    the key in Secrets" to mean the modules could use it. They can't —
    Secrets and key_providers are separate stores.

    This migration bridges the gap on the *next* startup: it walks every
    `app_secrets` row with a non-empty value, copies the encrypted
    blob into a `key_providers` row (one per secret name), and tags the
    description so the user can spot migrated rows in the API Keys
    tab. The original `app_secrets` row is left alone (the Secrets
    page still works as a generic store for proxy keys etc.).

    Idempotency: skipping when a `key_providers` row with the same name
    already exists makes re-runs safe. We don't try to detect "the
    value changed since the last migration" — the Secrets page is
    still the source of truth for legacy names; users who want a
    refresh can delete the migrated row and let the next startup
    re-create it.
    """
    rows = await fetch(
        "SELECT id, name, value_encrypted, description "
        "FROM app_secrets WHERE value_encrypted <> '' ORDER BY id ASC"
    )
    if not rows:
        return
    promoted = 0
    skipped = 0
    for row in rows:
        name = row["name"]
        # If a provider with the same name already exists (e.g. user
        # manually re-created it), don't touch it — they're now
        # responsible for keeping it in sync.
        existing = await fetchrow(
            "SELECT id FROM key_providers WHERE name = $1", name
        )
        if existing:
            skipped += 1
            continue
        desc = (
            f"Migrated from app_secrets (id={row['id']}) on startup. "
            f"Original description: {row['description'] or '(none)'.strip()}. "
            f"Manage from Config Center → API Keys."
        )
        await execute(
            """
            INSERT INTO key_providers (name, description, api_key_encrypted, enabled)
            VALUES ($1, $2, $3, TRUE)
            """,
            name,
            desc,
            row["value_encrypted"],
        )
        promoted += 1
        logger.info("Migrated app_secrets[%s]=%r into key_providers", row["id"], name)
    if promoted or skipped:
        logger.info(
            "Legacy app_secrets → key_providers: %d promoted, %d skipped (name already exists).",
            promoted, skipped,
        )


def _json(d: dict) -> str:
    import json
    return json.dumps(d, ensure_ascii=False)
