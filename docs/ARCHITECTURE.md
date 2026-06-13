# Architecture

## Big picture

```
┌────────────────────────────────────────────────────────────────────────┐
│ Browser (React 18 SPA)                                                 │
│   Studio · ConfigCenter · History · Secrets                            │
│   └─ TanStack-style fetch → /api/*                                     │
└────────────────────┬───────────────────────────────────────────────────┘
                     │  HTTP, JSON, single port 9060
┌────────────────────▼───────────────────────────────────────────────────┐
│ FastAPI (uvicorn, single-process)                                      │
│                                                                        │
│   Routers (api/*):                                                     │
│     health  configs  generate  history  secrets  media                 │
│                                                                        │
│   Services:                                                            │
│     generator.py ← unified request/response engine                     │
│       • render_template()  – substitute {{...}} placeholders           │
│       • _drop_unset()      – strip empty fields                        │
│       • _restore_typed_values()  – restore bool/int/float from ctx     │
│       • _apply_module_post_hooks()  – per-module wire-format fixes     │
│       • call_upstream()    – httpx POST + parse                        │
│       • _run_async_task()  – for video: submit → poll → retrieve → dl  │
│                                                                        │
│   Core:                                                                │
│     crypto.py     – Fernet encrypt/decrypt                             │
│     database.py   – asyncpg pool (JSONB handled by `::jsonb` casts)    │
│     config.py     – pydantic settings + YAML loader (config/database.yaml) │
└────────────────────┬───────────────────────────────────────────────────┘
                     │  asyncpg
┌────────────────────▼───────────────────────────────────────────────────┐
│ PostgreSQL 16+                                                         │
│   api_configs        (module, key_enc, base_url, model, templates…)    │
│   generation_history (module, prompt, req/resp payloads, files…)       │
│   app_secrets        (name, value_enc)                                 │
└────────────────────────────────────────────────────────────────────────┘
```

The frontend is a Vite-built SPA. `vite build` writes hashed bundles to `backend/static/`, which FastAPI mounts at `/` (with a no-store cache header on `index.html`).

## Data model

```sql
CREATE TABLE api_configs (
    id                SERIAL PRIMARY KEY,
    module            VARCHAR(50)  UNIQUE NOT NULL,   -- 'image' | 'voice' | 'music' | 'video'
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

CREATE TABLE generation_history (
    id               SERIAL PRIMARY KEY,
    module           VARCHAR(50)  NOT NULL,
    config_id        INTEGER      REFERENCES api_configs(id) ON DELETE SET NULL,
    prompt           TEXT         NOT NULL DEFAULT '',
    params           JSONB        NOT NULL DEFAULT '{}'::jsonb,
    request_payload  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    response_payload JSONB        NOT NULL DEFAULT '{}'::jsonb,
    output_files     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending',  -- pending|running|success|failed
    error_message    TEXT         NOT NULL DEFAULT '',
    duration_ms      INTEGER      NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_history_module_created ON generation_history(module, created_at DESC);

CREATE TABLE app_secrets (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) UNIQUE NOT NULL,
    value_encrypted TEXT         NOT NULL,
    description     TEXT         NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

The schema is `CREATE TABLE IF NOT EXISTS`, so the same migration script is safe to run on every backend boot.

### Why no asyncpg JSONB codec?

Installing `set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')` would let asyncpg return dicts automatically, **but** the column types already have `DEFAULT '{}'::jsonb` and the existing code uses `$1::jsonb` casts with pre-serialized JSON strings. Adding the codec would double-encode values. We keep things explicit instead — every JSONB column read comes back as a string and the route layer does `json.loads()` on the way out.

## Encryption

```
Fernet (AES-128-CBC + HMAC-SHA256, 128-bit tag)
└── Key from .master_key (auto-generated on first run, mode 0600)
        OR MASTER_KEY env var (preferred for production)

encrypt_str(plaintext: str) -> str   # URL-safe base64 ciphertext
decrypt_str(ciphertext: str) -> str  # raises on tamper / wrong key
```

The master key never leaves the host. It is **not** in the database. Losing it means re-pasting every API key.

## Placeholder syntax

Templates use `{{key}}` for substitution. Three forms are supported:

| Form | Example | Behaviour |
|------|---------|-----------|
| String | `{{voice_id}}` | Coerced to string; if empty/missing, renders as `""` (later stripped by `_drop_unset`) |
| Typed | `{{n:i\|1}}` | Coerced to int (`:i`), float (`:n`), bool (`:b`), or raw JSON (`:j`); the default after `\|` is used if the key is missing |
| String with default | `{{aspect_ratio:s\|1:1}}` | Same as string, with a default if the key is missing |

After substitution, the request is **scanned again** and any empty string / null / empty dict values are removed (`_drop_unset`). Then the leaf strings are replaced with their original typed values from the request context (`_restore_typed_values`) so the wire payload has correct JSON types (e.g. `6` not `"6"`, `true` not `"true"`).

Per-module post-hooks then fix any module-specific wire-format quirks — e.g. the video module strips `fast_pretreatment` when submode is `fl2v`, since the FL2V schema doesn't accept it.

## Request lifecycle (the happy path)

```
POST /api/generate/{module}    body: { prompt, params, config_id? }
  │
  ▼  load_config(module, config_id?)
config row from DB → ResolvedConfig
  │
  ▼  build_context(cfg, prompt, params)
ctx = { api_key, model, prompt, **default_params, **params }
  │
  ▼  build_request(cfg, prompt, params)
template render → drop_unset → restore_types → post_hooks
  │
  ▼  call_upstream(cfg, request_obj)      ← httpx, JSON body
HTTP 200 + JSON or binary body
  │
  ▼  parser dispatch
  jsonpath / openai_image / openai_audio / openai_video / minimax_music / binary / async_task
  │
  ▼  materialize
download URLs / decode hex / write to uploads/<module>/YYYY/MM/DD/<hash>.<ext>
  │
  ▼  persist
INSERT INTO generation_history (...) RETURNING *
  │
  ▼  return
GenerateResult { id, status, output_files, duration_ms, ... }
```

## Response parsers

| `type` | Used for | Pulls from response |
|--------|----------|---------------------|
| `jsonpath` | image / TTS-music jsonpath | `_jsonpath_lookup(parsed, items_path)` |
| `minimax_music` | speech-2.6+ / music-2.0 | decodes `data.audio` as hex → mp3 file |
| `binary` | legacy TTS that returned raw mp3 | writes body bytes directly |
| `async_task` | video (Hailuo) | submit → poll `query_path` → retrieve `file_id` → download |

JSONPath is a tiny subset: `$.data.image_urls`, `$.data[*]`, `$.data[0]`, `data.foo` (no `$` prefix also accepted).

## Why single-port, not Vite dev proxy?

- One process to manage in production
- `index.html` cache-busting is just a header
- The frontend's `import.meta.env` and `BASE_URL` are baked at build time, so we can use the same `http://localhost:9060/api/*` everywhere
- Vite dev server (`npm run dev`) is still useful during frontend-only iteration; just point its `server.proxy['/api']` to `:9060` (already configured in `vite.config.ts`).

## Failure modes

| Class | Behaviour |
|-------|-----------|
| DB unreachable | `/api/health` returns `db: false`; SPA shows a degraded banner |
| Bad API key | Upstream returns `code=1004`; we surface the message verbatim |
| Wrong model name | Upstream returns `code=2013`; same surfacing |
| Daily quota exhausted | Upstream returns `code=2056` with reset time; we surface verbatim |
| Network timeout | `httpx` raises; we wrap as `Upstream timeout after Xs` |
| Bad placeholder in template | `_coerce` returns `None`; the field is dropped, request still goes |

## Extension points

- **New module** (e.g. "embedding"): append a `SEED_CONFIGS` entry in `models.py` + add a form in `frontend/src/pages/configForms/` + register it in `App.tsx`'s `STUDIO_CHILDREN` and `MODULES` (the type union is `ModuleName` in `types/index.ts`).
- **New response parser type**: add a branch in `services/generator.py`'s parser dispatch (search for `if ptype ==`).
- **New placeholder type**: extend `_coerce` + `repl` in `render_template`.
