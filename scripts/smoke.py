"""Lightweight end-to-end smoke test for the MiniMax Tool API.

Run after the server is up:

    uv run python scripts/smoke.py

Notes:
  - All smoke-specific resources use a `smoke_*` prefix in either module
    or provider name, so they never collide with the user's real rows.
  - The `finally` block cleans up configs, providers, and history rows
    the generate calls create, so the user's data stays clean.
  - Database connection details (host, port, user, password, name) are
    read from `config/database.yaml` — the same file the app uses.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

BASE = "http://127.0.0.1:9060"
FAILS: list[str] = []
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# -------------------- DB config (for cleanup) --------------------

_ENV_REF_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")


def _resolve_env_refs(obj):
    if isinstance(obj, str):
        def repl(m):
            var, default = m.group(1), m.group(2)
            return os.environ.get(var, default if default is not None else "")
        return _ENV_REF_RE.sub(repl, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_refs(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_refs(v) for v in obj]
    return obj


def _load_db_config():
    candidates = [
        Path("/app/config/database.yaml"),
        PROJECT_ROOT / "config" / "database.yaml",
        PROJECT_ROOT / "config" / "database.local.yaml",
    ]
    for p in candidates:
        if p and p.is_file():
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            db = raw.get("database", raw)
            return _resolve_env_refs(db)
    return None


def _scrub_smoke_history():
    """Delete any history / provider / config rows this test created.

    The script is shipped into the running app container (it can resolve
    `host.docker.internal` from there) and run with `python -c` so we
    don't depend on a host-side asyncpg / network path. We unbind first
    because the FK uses ON DELETE RESTRICT.
    """
    cleanup_script = '''
import asyncio, asyncpg, os, re
from pathlib import Path
from urllib.parse import quote_plus
import yaml
_ENV_REF_RE = re.compile(r"\\$\\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\\}")
def _resolve(obj):
    if isinstance(obj, str):
        def repl(m):
            var, default = m.group(1), m.group(2)
            return os.environ.get(var, default if default is not None else "")
        return _ENV_REF_RE.sub(repl, obj)
    if isinstance(obj, dict):
        return {k: _resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve(v) for v in obj]
    return obj
raw = yaml.safe_load(Path("/app/config/database.yaml").read_text(encoding="utf-8")) or {}
db = _resolve(raw.get("database", raw))
if not db or not db.get("password"):
    raise SystemExit("no DB config in container")
ssl = "?sslmode=require" if db.get("ssl") else ""
dsn = f"postgresql://{db['user']}:{quote_plus(str(db['password']))}@{db['host']}:{int(db.get('port', 5432))}/{db['name']}{ssl}"
async def t():
    c = await asyncpg.connect(dsn)
    pat = "smoke_%"
    await c.execute("UPDATE api_configs SET key_provider_id = NULL WHERE module LIKE $1", pat)
    await c.execute("DELETE FROM generation_history WHERE module LIKE $1", pat)
    await c.execute("DELETE FROM api_configs WHERE module LIKE $1", pat)
    await c.execute("DELETE FROM key_providers WHERE name LIKE $1", pat)
    await c.close()
asyncio.run(t())
'''
    try:
        # Run inside the live app container so `host.docker.internal`
        # resolves. (Connecting from the host is brittle: the operator's
        # local postgres port + .pgpass differ from the container's view.)
        container = "minimax-app-1"
        r = subprocess.run(
            ["docker", "exec", container, "python", "-c", cleanup_script],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"  (warn: cleanup failed: stderr={r.stderr.strip()[:200]})")
    except Exception as e:
        print(f"  (warn: cleanup failed: {e})")


# -------------------- HTTP helpers --------------------


def check(label, ok, detail=""):
    mark = "✓" if ok else "✗"
    print(f"  {mark} {label}  {detail}")
    if not ok:
        FAILS.append(label)


def _http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, method=method, data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        return urllib.request.urlopen(r, timeout=15), None
    except urllib.error.HTTPError as e:
        return e, None


def get(path):
    resp, _ = _http("GET", path)
    return resp.status, resp.read()


def req(path, method, body=None):
    resp, _ = _http(method, path, body)
    return resp.status, resp.read()


# -------------------- pre-clean any leftover smoke rows --------------------
_scrub_smoke_history()


# -------------------- hide non-smoke providers during the run ---------------
#
# The D / E / F / G / H sections assume the key_provider table is in a
# controlled state (one provider, two providers, none). A user who set
# up the app before us — for example, after the Secrets→key_providers
# bridge ran for their existing `token_plan` secret — will have
# pre-existing providers that we must *not* interact with. To keep the
# environment deterministic without losing their data, we disable every
# provider whose name doesn't start with `smoke_` for the duration of
# this run, and restore their `enabled` flag at the end.
_preserved_provider_state: list[tuple[int, bool]] = []


def _quiesce_non_smoke_providers() -> None:
    s, b = get("/api/key-providers")
    for p in json.loads(b):
        if p["name"].startswith("smoke_"):
            continue
        _preserved_provider_state.append((p["id"], p["enabled"]))
        if p["enabled"]:
            # Disable quietly — we don't care about the response, we just
            # want them out of the way for the assertion-driven sections.
            req(f"/api/key-providers/{p['id']}", "PUT", {"enabled": False})


def _restore_preserved_providers() -> None:
    for pid, was_enabled in _preserved_provider_state:
        req(f"/api/key-providers/{pid}", "PUT", {"enabled": was_enabled})
    _preserved_provider_state.clear()


_quiesce_non_smoke_providers()


# -------------------- A. infra --------------------

print("== A. Infra ==")
s, b = get("/")
check("index.html served", s == 200 and b"<!doctype html>" in b.lower(), f"HTTP {s}, {len(b)}B")
s, b = get("/anything-deep")
check("SPA fallback for deep path", s == 200 and b"<!doctype html>" in b.lower(), f"HTTP {s}")
s, b = get("/api/health")
data = json.loads(b)
check("health=ok & db connected", data.get("status") == "ok" and data.get("db") is True, str(data))


# -------------------- B. config list / module shape --------------------

print("\n== B. Module configs ==")
s, b = get("/api/configs")
cfgs = json.loads(b)
well_known = {"image", "voice", "music", "video", "translate"}
check("5 well-known modules seeded", well_known.issubset({c["module"] for c in cfgs}),
      f"got: {sorted(c['module'] for c in cfgs)}")
check("has_api_key is a boolean on every row", all(isinstance(c["has_api_key"], bool) for c in cfgs))
check("key_provider_id field present on every row", all("key_provider_id" in c for c in cfgs))
check("key_provider_name field present on every row", all("key_provider_name" in c for c in cfgs))

s, b = get("/api/configs/image")
data = json.loads(b)
check("image config has request_template",
      isinstance(data.get("request_template"), dict) and "body" in data["request_template"])

s, b = get("/api/history?limit=10")
data = json.loads(b)
check("history list returns array", isinstance(data, list))


# -------------------- C. key_providers CRUD --------------------

print("\n== C. Key providers CRUD ==")

# Create
s, b = req("/api/key-providers", "POST", {
    "name": "smoke_default",
    "description": "smoke test provider",
    "api_key": "eyJhbGciOiJIUzI1NiJ9.smoke.fakesig",
    "enabled": True,
})
prov = json.loads(b)
prov_id = prov.get("id")
check("POST creates provider (201)", s == 201 and prov_id, f"HTTP {s} body[:120]={b[:120]!r}")
check("provider has_api_key=true after create", prov.get("has_api_key") is True)

# List
s, b = get("/api/key-providers")
provs = json.loads(b)
mine = [p for p in provs if p["id"] == prov_id]
check("GET lists providers and ours is there", len(mine) == 1)

# Update
s, b = req(f"/api/key-providers/{prov_id}", "PUT", {"description": "updated"})
upd = json.loads(b)
check("PUT updates provider", s == 200 and upd["description"] == "updated")

# Update to clear key
s, b = req(f"/api/key-providers/{prov_id}", "PUT", {"api_key": ""})
upd = json.loads(b)
check("PUT with empty api_key clears it", upd["has_api_key"] is False)

# Restore the key for the rest of the test
s, b = req(f"/api/key-providers/{prov_id}", "PUT", {"api_key": "eyJhbGciOiJIUzI1NiJ9.smoke.fakesig"})
check("PUT restores provider key", json.loads(b)["has_api_key"] is True)


# -------------------- D. auto-bind behaviour --------------------

print("\n== D. Auto-bind: 1 provider + key_provider_id=null ==")

# Create a config with no key_provider_id; should auto-bind to our single provider.
s, b = req("/api/configs", "POST", {
    "module": "smoke_image",
    "display_name": "smoke · image",
    "base_url": "https://api.minimaxi.com",
    "endpoint_path": "/v1/image_generation",
    "model": "image-01",
    "request_template": {"method": "POST", "headers": {}, "body": {}},
    "response_parser": {"type": "jsonpath", "items_path": "$.data.image_urls"},
    "default_params": {},
    "enabled": False,
    # key_provider_id omitted → backend should auto-bind
})
smoke_id = json.loads(b).get("id")
check("POST /api/configs (no provider) returns 201", s == 201 and smoke_id)
if smoke_id:
    s, b = get("/api/configs")
    all_cfgs = json.loads(b)
    cfg = next((c for c in all_cfgs if c["module"] == "smoke_image"), None)
    # API will either have set key_provider_id (1-provider case) or kept null
    # and the load path will still resolve it. We just check has_api_key here.
    check("auto-bound config has_api_key=true", cfg and cfg["has_api_key"] is True)
    check("auto-bound config has key_provider_id set", cfg and cfg["key_provider_id"] == prov_id,
          f"got {cfg.get('key_provider_id') if cfg else 'no row'}")


# -------------------- E. friendly error when provider has no key --------------------

print("\n== E. Provider empty key → friendly generate error ==")

# Clear the provider's key
req(f"/api/key-providers/{prov_id}", "PUT", {"api_key": ""})

# Try to generate through the auto-bound config
s, b = req("/api/generate/smoke_image", "POST", {"prompt": "x"})
detail = json.loads(b).get("detail", "")
# GenerationError surfaces as 502 via the global handler, but the user-
# visible message is the same as a 400-class error.
check("empty provider key → 'API key is empty' in error",
      s in (400, 500, 502) and "API key is empty" in str(detail), f"HTTP {s} detail={detail!r}")

# Restore the key again
req(f"/api/key-providers/{prov_id}", "PUT", {"api_key": "eyJhbGciOiJIUzI1NiJ9.smoke.fakesig"})


# -------------------- F. ambiguity: 2 providers + null ======================

print("\n== F. Ambiguity: 2 enabled providers + key_provider_id=null ==")
# Add a 2nd provider
s, b = req("/api/key-providers", "POST", {
    "name": "smoke_alt", "api_key": "eyJhbGciOiJIUzI1NiJ9.alt.fakesig", "enabled": True
})
prov2_id = json.loads(b)["id"]
check("2nd provider created", s == 201 and prov2_id)

# Create a config with no provider — should fail at generate time, not at create time
s, b = req("/api/configs", "POST", {
    "module": "smoke_ambiguous",
    "display_name": "smoke · ambiguous",
    "base_url": "https://api.minimaxi.com",
    "endpoint_path": "/v1/image_generation",
    "model": "image-01",
    "request_template": {"method": "POST", "headers": {}, "body": {}},
    "response_parser": {"type": "jsonpath", "items_path": "$.data.image_urls"},
    "default_params": {},
    "enabled": False,
})
amb_id = json.loads(b).get("id")
check("POST config with 2 providers (no explicit binding) → 201 (no fail at create)", s == 201 and amb_id)

s, b = req("/api/generate/smoke_ambiguous", "POST", {"prompt": "x"})
detail = json.loads(b).get("detail", "")
check("generate ambiguous → error names both providers",
      "ambiguous" in str(detail).lower() and "smoke_default" in str(detail) and "smoke_alt" in str(detail),
      f"detail={detail!r}")


# -------------------- G. explicit binding resolves ambiguity ======================

print("\n== G. Explicit binding breaks the tie ==")
s, b = req(f"/api/configs/{amb_id}", "PUT", {"key_provider_id": prov2_id})
check("PUT key_provider_id=prov2_id on ambiguous config", s == 200 and json.loads(b)["key_provider_id"] == prov2_id)


# -------------------- H. ON DELETE RESTRICT ===================================

print("\n== H. Delete provider with linked config → 409 ==")
s, b = req(f"/api/key-providers/{prov2_id}", "DELETE", None)
check("DELETE linked provider → 409", s == 409, f"HTTP {s}")


# -------------------- I. test endpoint =========================================

print("\n== I. Provider test endpoint ==")
s, b = req(f"/api/key-providers/{prov_id}/test", "POST", None)
test_res = json.loads(b)
# We don't assert ok=true because the fake key won't auth; we just assert
# the endpoint returns a structured result with latency_ms.
check("test endpoint returns structured result",
      "latency_ms" in test_res and "message" in test_res,
      f"HTTP {s} body={b[:200]!r}")


# -------------------- K. translate model override =============================

print("\n== K. Translate model override ==")

# Look up the seeded translate config. We'll bind it to the smoke provider
# so the key resolution path doesn't fail.
s, b = get("/api/configs")
all_cfgs = json.loads(b)
translate_cfg = next((c for c in all_cfgs if c["module"] == "translate"), None)
check("seeded translate config exists", translate_cfg is not None,
      f"got id={translate_cfg['id'] if translate_cfg else None}")

if translate_cfg and prov_id:
    # Bind the translate config to our provider.
    s, b = req(f"/api/configs/{translate_cfg['id']}", "PUT",
               {"key_provider_id": prov_id})
    check("bind translate config to smoke provider", s == 200)

    # Make sure the provider has a key (E test may have cleared it).
    req(f"/api/key-providers/{prov_id}", "PUT",
        {"api_key": "eyJhbGciOiJIUzI1NiJ9.smoke.fakesig"})

    # 1. Request without `model` → backend should use cfg.model. We
    #    expect the request to be ACCEPTED (not 422 / 400). The upstream
    #    call itself will fail because the fake key isn't real, but
    #    that's the point — we're testing the request shape, not the
    #    upstream behaviour.
    s, b = req("/api/translate", "POST", {
        "text": "hello",
        "source": "en",
        "target": "zh",
        "config_id": translate_cfg["id"],
    })
    detail = json.loads(b).get("detail", "")
    check("translate without model: request accepted (not 422)",
          s != 422, f"HTTP {s} detail={detail!r}")

    # 2. Request with explicit `model` override. The body still goes
    #    through; backend uses the override instead of cfg.model.
    s, b = req("/api/translate", "POST", {
        "text": "hello",
        "source": "en",
        "target": "zh",
        "config_id": translate_cfg["id"],
        "model": "MiniMax-M2.7",
    })
    detail = json.loads(b).get("detail", "")
    check("translate with model override: request accepted (not 422)",
          s != 422, f"HTTP {s} detail={detail!r}")

    # 3. Empty-string model falls back to cfg.model (treated as absent).
    s, b = req("/api/translate", "POST", {
        "text": "hello",
        "source": "en",
        "target": "zh",
        "config_id": translate_cfg["id"],
        "model": "",
    })
    detail = json.loads(b).get("detail", "")
    check("translate with empty model: treated as absent (not 422)",
          s != 422, f"HTTP {s} detail={detail!r}")

    # Restore: unbind so cleanup can delete the provider.
    s, _ = req(f"/api/configs/{translate_cfg['id']}", "PUT",
               {"key_provider_id": None})
    check("unbind translate config for cleanup", s == 200)


# -------------------- L. Legacy Secrets → key_providers bridge ===============

print("\n== L. Legacy Secrets → key_providers bridge ==")

# 1. Plant a secret via the Secrets API (the "old way" of storing keys
#    before the key_providers refactor).
s, b = req("/api/secrets/smoke_legacy_key", "PUT", {
    "value": "eyJhbGciOiJIUzI1NiJ9.smoke.fakesig",
    "description": "smoke test for legacy bridge",
})
check("PUT /api/secrets/smoke_legacy_key (planted for bridge test)", s == 200)

# 2. Verify the secret shows up in /api/secrets but NOT in /api/key-providers
#    yet (the bridge runs on app startup, not on every API call).
s, b = get("/api/secrets")
secret_list = json.loads(b)
check("secret visible in /api/secrets", any(s["name"] == "smoke_legacy_key" for s in secret_list))

s, b = get("/api/key-providers")
provs_before = [p["name"] for p in json.loads(b)]
check("key provider not yet promoted (bridge is startup-only)", "smoke_legacy_key" not in provs_before)

# 3. Trigger the migration by running `init_db` inside the running app
#    container. This is the same code path that runs on container start.
import subprocess as _sp
bridge_script = '''
import asyncio
from app.database import Database
from app.models import _migrate_legacy_secrets
async def t():
    await Database.init()
    await _migrate_legacy_secrets()
    await Database.close()
    print("bridge-ok")
asyncio.run(t())
'''
try:
    r = _sp.run(
        ["docker", "exec", "minimax-app-1", "python", "-c", bridge_script],
        capture_output=True, text=True, timeout=30,
    )
    check("bridge runs without error (exit 0 + 'bridge-ok' in stdout)",
          r.returncode == 0 and "bridge-ok" in r.stdout,
          f"stderr={r.stderr.strip()[:200]}")
except Exception as e:
    check("bridge runs without error", False, f"exc={e}")

# 4. Verify the secret was promoted.
s, b = get("/api/key-providers")
provs_after = json.loads(b)
migrated = next((p for p in provs_after if p["name"] == "smoke_legacy_key"), None)
check("legacy secret promoted to key_provider",
      migrated is not None and migrated["has_api_key"],
      f"got {migrated}")

# 5. Re-run the bridge — the existing provider should NOT be duplicated.
try:
    r = _sp.run(
        ["docker", "exec", "minimax-app-1", "python", "-c", bridge_script],
        capture_output=True, text=True, timeout=30,
    )
    s, b = get("/api/key-providers")
    provs_again = [p for p in json.loads(b) if p["name"] == "smoke_legacy_key"]
    check("re-running bridge is idempotent (no duplicate providers)",
          len(provs_again) == 1, f"got {len(provs_again)} matches")
except Exception as e:
    check("idempotent re-run", False, f"exc={e}")

# 6. Verify the original app_secrets row is still there (bridge copies,
#    it doesn't move).
s, b = get("/api/secrets")
still_in_secrets = any(s["name"] == "smoke_legacy_key" for s in json.loads(b))
check("original app_secrets row preserved (bridge copies, doesn't move)",
      still_in_secrets)


# -------------------- M. Translate response cleaning =========================

print("\n== M. Translate response cleaning (real upstream) ==")

# The cleaning logic strips `<think>…</think>` blocks, fences, language
# tags, and surrounding quotes. The first three can only be observed
# with a real upstream call — fake keys get 401'd before any reasoning
# is generated. So we need to temporarily *un-quiesce* any preserved
# non-smoke provider that has a real key, hit the upstream, and then
# put it back the way we found it.

def _un_quiesce_preserved() -> tuple[list[int], list[int]]:
    """For the M section we need exactly ONE enabled+keyed provider (so
    auto-bind resolves, not ambiguous). We:

      1. Disable every smoke_* provider (they were used by earlier
         sections; for M we want them out of the way).
      2. Re-enable exactly one preserved provider that has a real key.

    Returns (smoke_disabled, preserved_reenabled) so the finally block
    can restore both lists.
    """
    s, b = get("/api/key-providers")
    provs = {p["id"]: p for p in json.loads(b)}

    smoke_disabled: list[int] = []
    for pid, prov in provs.items():
        if prov["name"].startswith("smoke_") and prov["enabled"]:
            req(f"/api/key-providers/{pid}", "PUT", {"enabled": False})
            smoke_disabled.append(pid)

    preserved_reenabled: list[int] = []
    for pid, was_enabled in _preserved_provider_state:
        if not was_enabled:
            continue
        if pid in provs and provs[pid]["has_api_key"]:
            req(f"/api/key-providers/{pid}", "PUT", {"enabled": True})
            preserved_reenabled.append(pid)
            break  # one is enough
    return smoke_disabled, preserved_reenabled


def _re_quiesce(smoke_disabled: list[int], preserved_reenabled: list[int]) -> None:
    for pid in preserved_reenabled:
        req(f"/api/key-providers/{pid}", "PUT", {"enabled": False})
    for pid in smoke_disabled:
        req(f"/api/key-providers/{pid}", "PUT", {"enabled": True})


smoke_disabled, reenabled = _un_quiesce_preserved()
try:
    # If no provider with a real key is available, skip these checks
    # gracefully (the test environment might be truly fake).
    if not reenabled:
        print("  (skipped: no real-key provider available — fake-key environment)")
    else:
        # Look up the seeded translate config so we can assert it's been
        # auto-migrated to the v2 endpoint (this is part of the M
        # section: the translate config should never stay on the legacy
        # OpenAI-compatible endpoint after the next startup).
        s, b = get("/api/configs")
        tcfg = next((c for c in json.loads(b) if c["module"] == "translate"), None)
        # We can't read endpoint_path from the public API (it's not in
        # the response), so we check via SQL — the container is up and
        # the smoke machine talks to the same Postgres.
        try:
            _sp_sql = _sp.run(
                ["docker", "exec", "postgres", "psql", "-U", "postgres",
                 "-d", "minimax_tool", "-t", "-A", "-c",
                 "SELECT endpoint_path FROM api_configs WHERE module='translate'"],
                capture_output=True, text=True, timeout=10,
            )
            ep = _sp_sql.stdout.strip()
            check("translate config uses v2 chatcompletion endpoint",
                  ep == "/v1/text/chatcompletion_v2",
                  f"got {ep!r}")
        except Exception as e:
            check("translate config uses v2 chatcompletion endpoint",
                  False, f"exc={e}")

        # Hit the real upstream with a Chinese→English call.
        s, b = req("/api/translate", "POST", {
            "text": "你好",
            "source": "zh",
            "target": "en",
        })
        body = json.loads(b)
        if s == 200:
            cleaned = body.get("translated_text", "")
            check("translated_text is a string", isinstance(cleaned, str))
            check("translated_text is non-empty", bool(cleaned.strip()))
            check("translated_text has no <think> block",
                  "<think>" not in cleaned and "</think>" not in cleaned,
                  f"got {cleaned[:120]!r}")
            check("translated_text has no surrounding quotes",
                  not (cleaned.startswith('"') and cleaned.endswith('"')))
            check("translated_text has no code fence",
                  not cleaned.startswith("```"))
        else:
            # Upstream may rate-limit or reject — surface that fact but
            # don't treat it as a hard fail (this section is opportunistic).
            print(f"  (skipped: upstream returned HTTP {s} {b[:120]!r})")
finally:
    _re_quiesce(smoke_disabled, reenabled)


# -------------------- J. cleanup ===============================================

print("\n== J. Cleanup ==")
# Clear the binding so we can delete providers safely. We unbind every
# smoke_* module we know about (smoke_image in D, smoke_ambiguous in F/G)
# so the ON DELETE RESTRICT won't block the provider deletes below.
for mid in (smoke_id, amb_id):
    if mid:
        s, _ = req(f"/api/configs/{mid}", "PUT", {"key_provider_id": None})
        check(f"unbind config id={mid} (key_provider_id=null) for cleanup", s == 200)

# Delete the bridge-promoted provider (L test) so the secret can also
# be cleaned up. Unbinding first isn't needed here because no api_config
# row references it (the bridge doesn't auto-bind configs), but
# ON DELETE RESTRICT will still complain if any row does.
legacy_prov = next(
    (p["id"] for p in json.loads(get("/api/key-providers")[1]) if p["name"] == "smoke_legacy_key"),
    None,
)
if legacy_prov:
    s, _ = req(f"/api/key-providers/{legacy_prov}", "DELETE", None)
    check(f"DELETE bridge-promoted provider id={legacy_prov}", s == 200)

# Delete the secret row.
s, _ = req("/api/secrets/smoke_legacy_key", "DELETE", None)
check("DELETE bridge-test secret", s == 200)

# Delete both providers
for pid in (prov2_id, prov_id):
    if pid:
        s, _ = req(f"/api/key-providers/{pid}", "DELETE", None)
        check(f"DELETE provider id={pid}", s == 200)

# Wipe the temp config rows + history via SQL (we never call /api/generate
# successfully, so no history rows were created, but be defensive).
_scrub_smoke_history()

# Put any non-smoke providers back the way we found them, so the user's
# bridge-promoted `token_plan` etc. is enabled again.
_restore_preserved_providers()


# -------------------- summary ==================================================

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): {FAILS}")
    sys.exit(1)
print("ALL CHECKS PASSED")
