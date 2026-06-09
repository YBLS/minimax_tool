"""Debug: walk video generation step by step. Print HTTP code + first 400B
of each response, NEVER the API key.

Steps: submit -> poll loop -> retrieve -> download URL.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from app.config import get_settings
from app.crypto import decrypt_str
from app.database import Database


def _truncate(b: bytes, n: int = 400) -> str:
    try:
        s = b.decode("utf-8", errors="replace")
    except Exception:
        s = repr(b)
    return s[:n]


async def main() -> None:
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT api_key_encrypted, base_url, model, request_template, "
                "       response_parser "
                "FROM api_configs WHERE module = 'video'",
            )
        if not row or not row["api_key_encrypted"]:
            print("video config has no api_key, aborting")
            return
        api_key = decrypt_str(row["api_key_encrypted"])
        masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        base = row["base_url"].rstrip("/")
        model = row["model"]
        template = row["request_template"]
        parser = row["response_parser"]
        if isinstance(template, str):
            template = json.loads(template)
        if isinstance(parser, str):
            parser = json.loads(parser)

        # Step 1: submit
        submit_body = {
            "model": model,
            "prompt": "a single yellow sunflower turning slowly in the wind, blue sky, cinematic",
        }
        submit_path = template["body"].get("__path__", "/v1/video_generation")
        # In our case endpoint_path is in api_configs but template only has body.
        # Use the seed-known path:
        submit_path = "/v1/video_generation"
        url = base + submit_path
        print(f"[1] submit POST {url}  model={model}  auth={masked}")
        async with httpx.AsyncClient(timeout=180.0) as client:
            r1 = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json=submit_body,
            )
        print(f"    HTTP {r1.status_code}  ct={r1.headers.get('content-type')}  bytes={len(r1.content)}")
        print(f"    body: {_truncate(r1.content)}")
        if r1.status_code >= 400:
            return
        j1 = r1.json()
        task_id = j1.get("task_id")
        if not task_id:
            print("    no task_id, aborting")
            return
        print(f"    task_id = {task_id}")
        print()

        # Step 2: poll
        poll_path = parser.get("query_path", "/v1/query/video_generation")
        poll_url = base + poll_path
        print(f"[2] poll GET {poll_url}  task_id={task_id}")
        deadline = time.time() + 300
        file_id = None
        last_status = None
        async with httpx.AsyncClient(timeout=180.0) as client:
            while time.time() < deadline:
                await asyncio.sleep(5)
                r2 = await client.get(
                    poll_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"task_id": task_id},
                )
                if r2.status_code >= 400:
                    print(f"    HTTP {r2.status_code}: {_truncate(r2.content)}")
                    continue
                j2 = r2.json()
                last_status = j2.get("status") or (j2.get("data") or {}).get("status")
                print(f"    status={last_status}  bytes={len(r2.content)}  body={_truncate(r2.content, 200)}")
                if isinstance(last_status, str) and last_status.lower() in {"success", "finished", "completed"}:
                    file_id = j2.get("file_id") or (j2.get("data") or {}).get("file_id")
                    break
                if isinstance(last_status, str) and last_status.lower() in {"fail", "failed"}:
                    print("    task failed, aborting")
                    return
        if not file_id:
            print(f"    no file_id after polling, last status={last_status}")
            return
        print(f"    file_id = {file_id}")
        print()

        # Step 3: retrieve
        d_path = parser.get("download_path", "/v1/files/retrieve")
        d_url = base + d_path
        d_method = parser.get("download_method", "POST")
        d_body = parser.get("download_body") or {"file_id": "{{file_id}}"}
        # Substitute
        d_body = {k: (v.replace("{{file_id}}", str(file_id)) if isinstance(v, str) else v)
                  for k, v in d_body.items()}
        print(f"[3] retrieve {d_method} {d_url}  body={d_body}")
        async with httpx.AsyncClient(timeout=180.0) as client:
            r3 = await client.request(
                d_method, d_url,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json=d_body,
            )
        print(f"    HTTP {r3.status_code}  ct={r3.headers.get('content-type')}  bytes={len(r3.content)}")
        print(f"    body: {_truncate(r3.content, 800)}")
        if r3.status_code < 400:
            try:
                j3 = r3.json()
                # Look for download URL
                for path in ["$.file.download_url", "$.data.file.download_url",
                             "$.download_url", "$.data.download_url",
                             "$.file.url", "$.url"]:
                    import re
                    m = re.match(r"\$\.(.+)", path)
                    cur = j3
                    for seg in (m.group(1).split(".") if m else []):
                        if isinstance(cur, dict) and seg in cur:
                            cur = cur[seg]
                        else:
                            cur = None
                            break
                    if cur:
                        print(f"    download_url ({path}) = {cur}")
            except Exception as e:
                print(f"    (json parse failed: {e})")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
