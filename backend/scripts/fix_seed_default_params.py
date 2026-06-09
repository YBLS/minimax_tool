"""One-shot: refresh default_params for music + image to match latest seed.
Re-runnable / idempotent.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Database


FIXES = {
    "music": {
        "lyrics": "[Instrumental]",
        "format": "mp3",
        "sample_rate": 32000,
        "bitrate": 128000,
    },
}


async def main() -> None:
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            for module, params in FIXES.items():
                result = await conn.execute(
                    "UPDATE api_configs SET default_params = $1::jsonb "
                    "WHERE module = $2",
                    json.dumps(params), module,
                )
                print(f"  {module}: {result}")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
