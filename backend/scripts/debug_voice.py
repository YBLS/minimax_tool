"""Debug helper: decrypt the voice config's API key, call /v1/t2a_v2 directly,
print only the HTTP status, content-type, and first ~300 bytes of the body.
NEVER print the API key itself.

Usage:  uv run python scripts/debug_voice.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from app.config import get_settings
from app.crypto import decrypt_str
from app.database import Database


async def main() -> None:
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT api_key_encrypted, base_url, endpoint_path, model, "
                "       request_template "
                "FROM api_configs WHERE module = 'voice'",
            )
        if not row or not row["api_key_encrypted"]:
            print("voice config has no api_key, aborting")
            return

        api_key = decrypt_str(row["api_key_encrypted"])
        # Mask the key for the printed Authorization header
        masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 12 else "***"

        # Build the request body exactly like generator.py does
        body = {
            "model": row["model"],
            "text": "今天天气不错",
            "voice_setting": {
                "voice_id": "female-shaonv",
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }

        url = row["base_url"].rstrip("/") + row["endpoint_path"]
        print(f"POST {url}")
        print(f"  model = {row['model']}")
        print(f"  auth  = Bearer {masked}")
        print(f"  body  = {body}")
        print()

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        print(f"HTTP {resp.status_code}")
        print(f"content-type: {resp.headers.get('content-type')}")
        print(f"content-length: {resp.headers.get('content-length')}")
        body_bytes = resp.content
        print(f"actual body bytes: {len(body_bytes)}")
        if body_bytes:
            print("--- body (first 400 bytes) ---")
            try:
                print(body_bytes[:400].decode("utf-8", errors="replace"))
            except Exception:
                print(repr(body_bytes[:400]))
            print("--- end ---")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
