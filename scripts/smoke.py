"""Lightweight end-to-end smoke test for the MiniMax Tool API.

Run after the server is up:

    uv run python scripts/smoke.py

Notes:
  - All smoke-specific configs use module names starting with `smoke_` so they
    never collide with the user's real `image`/`voice`/`music`/`video` configs.
  - The `finally` block cleans up both the temp config rows AND the
    generation_history rows the generate calls create, so the user's history
    stays clean.
"""

import json
import urllib.request
import urllib.error
import subprocess

BASE = "http://127.0.0.1:9060"
FAILS = []


def check(label, ok, detail=""):
    mark = "✓" if ok else "✗"
    print(f"  {mark} {label}  {detail}")
    if not ok:
        FAILS.append(label)


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def req(path, method, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, method=method, data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _scrub_smoke_history():
    """Delete any history rows the generate calls in this test created."""
    try:
        r = subprocess.run(
            ["uv", "run", "python", "-c", '''
import asyncio, asyncpg
from urllib.parse import quote_plus
async def t():
    c = await asyncpg.connect(f"postgresql://postgres:{quote_plus('p@ssw0rd')}@localhost:5432/minimax_tool")
    await c.execute("DELETE FROM generation_history WHERE module LIKE 'smoke_%'")
    await c.close()
asyncio.run(t())
'''],
            cwd="/Volumes/ExtentData/HelloWorld/MinimaxTool/backend",
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"  (warn: smoke history cleanup failed: {r.stderr.strip()[:200]})")
    except Exception as e:
        print(f"  (warn: smoke history cleanup failed: {e})")


# -- pre-clean any leftover smoke rows from a previous failed run
_scrub_smoke_history()

print("== SPA & assets ==")
s, b = get("/")
check("index.html served", s == 200 and b"<!doctype html>" in b.lower(), f"HTTP {s}, {len(b)}B")
s, b = get("/anything-deep")
check("SPA fallback for deep path", s == 200 and b"<!doctype html>" in b.lower(), f"HTTP {s}")

print("\n== API contracts ==")
s, b = get("/api/health")
data = json.loads(b)
check("health=ok & db connected", data.get("status") == "ok" and data.get("db") is True, str(data))

s, b = get("/api/configs")
data = json.loads(b)
check("4 modules seeded", len(data) == 4, f"{len(data)} rows")
check("has_api_key is a boolean on every row", all(isinstance(c["has_api_key"], bool) for c in data))

s, b = get("/api/configs/image")
data = json.loads(b)
check("image config has request_template",
      isinstance(data.get("request_template"), dict) and "body" in data["request_template"])

s, b = get("/api/history?limit=10")
data = json.loads(b)
check("history list returns array", isinstance(data, list))

print("\n== Write path ==")
# Use a dedicated "smoke_image" module so the user's real `image` config
# (which may already have a real API key) is never touched.
smoke_id = None
smoke_keyless_id = None
try:
    s, b = req("/api/configs", "POST", {
        "module": "smoke_image",
        "display_name": "smoke · image",
        "base_url": "https://api.minimaxi.com",
        "endpoint_path": "/v1/image_generation",
        "model": "image-01",
        "api_key": "sk-smoke-initial",
        "request_template": {"method": "POST", "headers": {}, "body": {}},
        "response_parser": {"type": "jsonpath", "items_path": "$.data.image_urls"},
        "default_params": {},
        "enabled": False,
    })
    check("POST creates config", s == 201, f"HTTP {s}, body[:120]={b[:120]!r}")
    smoke_id = json.loads(b)["id"]

    s, b = req(f"/api/configs/{smoke_id}", "PUT", {"api_key": "sk-smoke-test"})
    data = json.loads(b)
    check("PUT updates config (has_api_key flips on)", data["has_api_key"] is True)

    s, b = req(f"/api/configs/{smoke_id}", "PUT", {"api_key": ""})
    data = json.loads(b)
    check("PUT with empty api_key clears it", data["has_api_key"] is False)

    s, b = req("/api/generate/image", "POST", {"prompt": ""})
    check("empty prompt → 422", s == 422)

    # Test "no key → friendly error" using a dedicated keyless config so the
    # user's real image config (which may have a working key) is never touched,
    # and so we don't wait on an actual upstream call that may take >20s.
    s, b = req("/api/configs", "POST", {
        "module": "smoke_keyless",
        "display_name": "smoke · keyless",
        "base_url": "https://api.minimaxi.com",
        "endpoint_path": "/v1/image_generation",
        "model": "image-01",
        "api_key": "",   # no key on purpose
        "request_template": {"method": "POST", "headers": {}, "body": {}},
        "response_parser": {"type": "jsonpath", "items_path": "$.data.image_urls"},
        "default_params": {},
        "enabled": False,
    })
    smoke_keyless_id = json.loads(b)["id"]
    s, b = req("/api/generate/smoke_keyless", "POST", {"prompt": "x"})
    data = json.loads(b)
    check("no key → friendly error", "API key is empty" in str(data), str(data)[:120])
finally:
    # Always clean up — even if a check fails or the test crashes.
    if smoke_id is not None:
        try: req(f"/api/configs/{smoke_id}", "DELETE")
        except: pass
    if smoke_keyless_id is not None:
        try: req(f"/api/configs/{smoke_keyless_id}", "DELETE")
        except: pass
    # Scrub the history rows the generate calls wrote (in a separate process
    # since this script doesn't have asyncpg).
    _scrub_smoke_history()

print()
if FAILS:
    print(f"FAILED: {FAILS}")
    raise SystemExit(1)
print("ALL CHECKS PASSED")
