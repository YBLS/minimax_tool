"""End-to-end smoke test that runs inside the docker container.

Mirrors scripts/smoke.py but talks to the running uvicorn process
over loopback instead of the host:port, so it works in any environment.

Uses a unique module name per run (timestamp suffix) so repeated runs
don't collide on the api_configs.module UNIQUE constraint.
"""
import json
import sys
import time
import urllib.error
import urllib.request


def http(method, path, body=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:9060{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        return urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as e:
        return e


def main() -> int:
    checks = []

    r = http("GET", "/")
    checks.append(("SPA served", r.status == 200))

    r = http("GET", "/some/deep/spa/path")
    checks.append(("SPA fallback for deep path", r.status == 200))

    r = http("GET", "/api/health")
    h = json.loads(r.read())
    checks.append(("health=ok & db connected", h["status"] == "ok" and h["db"]))

    r = http("GET", "/api/configs")
    cfgs = json.loads(r.read())
    # ≥4 well-known modules; test isolation rows may have been left behind.
    well_known = {"image", "voice", "music", "video"}
    checks.append(
        ("4 well-known modules seeded", well_known.issubset({c["module"] for c in cfgs}))
    )
    checks.append(
        ("has_api_key is a boolean on every row",
         all(isinstance(c["has_api_key"], bool) for c in cfgs))
    )
    checks.append(
        ("image config has request_template", "request_template" in cfgs[0])
    )

    r = http("GET", "/api/history")
    checks.append(("history list returns array", isinstance(json.loads(r.read()), list)))

    # Create with a unique module name so re-runs don't collide.
    smod = f"smoke_docker_{int(time.time() * 1000)}"
    r = http(
        "POST", "/api/configs",
        {
            "module": smod,
            "display_name": "smoke · docker",
            "base_url": "https://api.minimaxi.com",
            "endpoint_path": "/v1/image_generation",
            "model": "image-01",
            "request_template": {"method": "POST", "headers": {}, "body": {}},
            "response_parser": {"type": "jsonpath", "items_path": "$.data.image_urls"},
        },
    )
    body = r.read()
    new = json.loads(body)
    new_id = new.get("id")
    checks.append(("POST creates config (201)", r.status == 201 and new_id))

    # Update with key
    r = http(
        "PUT", f"/api/configs/{new_id}",
        {
            "api_key": "smoke-key",
            "request_template": {"method": "POST", "headers": {}, "body": {}},
            "response_parser": {"type": "jsonpath", "items_path": "$.data.image_urls"},
        },
    )
    upd = json.loads(r.read())
    checks.append(("PUT updates + has_api_key flips on", r.status == 200 and upd["has_api_key"]))

    # Clear key
    r = http(
        "PUT", f"/api/configs/{new_id}",
        {
            "api_key": "",
            "request_template": {"method": "POST", "headers": {}, "body": {}},
            "response_parser": {"type": "jsonpath", "items_path": "$.data.image_urls"},
        },
    )
    upd = json.loads(r.read())
    checks.append(("PUT with empty api_key clears it", r.status == 200 and not upd["has_api_key"]))

    # Empty prompt
    r = http("POST", "/api/generate/image", {"prompt": ""})
    checks.append(("empty prompt → 422", r.status == 422))

    # No key
    r = http("POST", "/api/generate/image", {"prompt": "hello"})
    detail = json.loads(r.read()).get("detail", "")
    checks.append(("no key → friendly error", "API key is empty" in detail))

    # Cleanup
    http("DELETE", f"/api/configs/{new_id}")

    print()
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    print()
    if all(ok for _, ok in checks):
        print("ALL CHECKS PASSED")
        return 0
    print("FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
