"""Update video response_parser download_method from POST to GET.

Discovered (2025-12): MiniMax's /v1/files/retrieve is documented as GET, not
POST. The POST version returns 404 "404 page not found" (consuming nothing
beyond the failed request, but breaking the flow). Fix is one-line: change
download_method to GET — the rest of the flow already works correctly
(submit, poll, file_id extraction).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Database


async def main() -> None:
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, module, response_parser "
                "FROM api_configs WHERE module = 'video'",
            )
            if not row:
                print("No video config found, aborting")
                return
            current = row["response_parser"]
            if isinstance(current, str):
                current = json.loads(current)
            if current.get("download_method") == "GET":
                print("already GET, nothing to do")
                return
            current["download_method"] = "GET"
            result = await conn.execute(
                "UPDATE api_configs SET response_parser = $1::jsonb "
                "WHERE module = 'video'",
                json.dumps(current),
            )
            print(f"{result}: download_method -> GET")
            row2 = await conn.fetchrow(
                "SELECT response_parser FROM api_configs WHERE module = 'video'",
            )
            print(f"after: {row2['response_parser']}")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
