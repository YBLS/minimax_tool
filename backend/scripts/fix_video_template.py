"""One-shot: replace the video config's request_template + default_params with
the full T2V / I2V / FL2V body, then verify the existing api_key_encrypted
is preserved.

Re-runnable.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Database


NEW_REQUEST_TEMPLATE = {
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
}

NEW_DEFAULT_PARAMS = {
    "duration": 6,
    "resolution": "768P",
    "prompt_optimizer": True,
    "aigc_watermark": False,
}


async def main() -> None:
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, model, api_key_encrypted, request_template, default_params "
                "FROM api_configs WHERE module = 'video'",
            )
            if not row:
                print("No video config found, aborting")
                return
            print(f"id={row['id']} model={row['model']} has_key={bool(row['api_key_encrypted'])}")
            rt = row['request_template']
            if isinstance(rt, str):
                rt = json.loads(rt)
            print(f"  before request_template body keys: {sorted((rt or {}).get('body', {}).keys())}")
            await conn.execute(
                "UPDATE api_configs SET request_template = $1::jsonb, default_params = $2::jsonb "
                "WHERE module = 'video'",
                json.dumps(NEW_REQUEST_TEMPLATE), json.dumps(NEW_DEFAULT_PARAMS),
            )
            row2 = await conn.fetchrow(
                "SELECT model, api_key_encrypted, request_template, default_params "
                "FROM api_configs WHERE module = 'video'",
            )
            rt2 = row2['request_template']
            if isinstance(rt2, str):
                rt2 = json.loads(rt2)
            print(f"  after request_template body keys: {sorted(rt2['body'].keys())}")
            print(f"  default_params: {row2['default_params']}")
            print(f"  has_key after: {bool(row2['api_key_encrypted'])}")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
