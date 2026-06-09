"""Update voice's response_parser from {type: binary} to {type: minimax_music}.

Discovery (2025-12): MiniMax's /v1/t2a_v2 with speech-2.6-turbo now returns
{ "data": { "audio": "<hex>" } } — same shape as /v1/music_generation —
instead of the raw binary mp3 we used to get with the old speech-01-turbo
model. The minimax_music parser already handles hex decode, so we just
re-point voice to it.

Run once, idempotent.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Database


NEW_PARSER = {
    "type": "minimax_music",
    "items_path": "$.data",
    "default_ext": "mp3",
}


async def main() -> None:
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, module, model, response_parser "
                "FROM api_configs WHERE module = 'voice'",
            )
            if not row:
                print("No voice config found, aborting")
                return
            current = row["response_parser"]
            if isinstance(current, str):
                current = json.loads(current)
            print(f"id={row['id']} module={row['module']} model={row['model']}")
            print(f"  before: {current}")
            if current == NEW_PARSER:
                print("  already up-to-date, nothing to do")
                return
            result = await conn.execute(
                "UPDATE api_configs SET response_parser = $1::jsonb "
                "WHERE module = 'voice'",
                json.dumps(NEW_PARSER),
            )
            print(f"  {result}")
            row2 = await conn.fetchrow(
                "SELECT response_parser FROM api_configs WHERE module = 'voice'",
            )
            print(f"  after:  {row2['response_parser']}")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
