"""One-shot script: update model + display_name for the 3 stale seed configs.

Voice (id=14), Music (id=15), Video (id=16) were seeded with retired model
names (speech-01-turbo / music-01 / video-01) that the upstream API no longer
accepts. We update ONLY the model and display_name columns, leaving
api_key_enc / has_api_key / templates / etc. untouched so the user's already-
filled API keys are preserved.

Safe to re-run — uses the latest model names as canonical values.

Run from the backend/ directory:
    uv run python scripts/fix_seed_models.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `import app.*` when run from backend/
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.database import Database  # noqa: E402


# (module, model, display_name)
FIXES = [
    ("voice", "speech-2.6-turbo",   "Voice · speech-2.6-turbo"),
    ("music", "music-2.0",          "Music · music-2.0"),
    ("video", "MiniMax-Hailuo-02",  "Video · MiniMax-Hailuo-02"),
]


async def main() -> None:
    s = get_settings()
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            # Show before
            rows = await conn.fetch(
                "SELECT id, module, model, display_name, "
                "       (api_key_encrypted <> '') AS has_key "
                "FROM api_configs WHERE module = ANY($1::text[]) "
                "ORDER BY id",
                [m for m, _, _ in FIXES],
            )
            print("BEFORE:")
            for r in rows:
                print(f"  id={r['id']:>3} module={r['module']:<7} "
                      f"model={r['model']:<25} has_key={r['has_key']}  "
                      f"display_name={r['display_name']}")
            print()

            for module, model, display_name in FIXES:
                result = await conn.execute(
                    "UPDATE api_configs SET model = $1, display_name = $2 "
                    "WHERE module = $3",
                    model, display_name, module,
                )
                # result is "UPDATE n"
                print(f"  {module}: {result}")

            print()
            # Show after
            rows = await conn.fetch(
                "SELECT id, module, model, display_name, "
                "       (api_key_encrypted <> '') AS has_key "
                "FROM api_configs WHERE module = ANY($1::text[]) "
                "ORDER BY id",
                [m for m, _, _ in FIXES],
            )
            print("AFTER:")
            for r in rows:
                print(f"  id={r['id']:>3} module={r['module']:<7} "
                      f"model={r['model']:<25} has_key={r['has_key']}  "
                      f"display_name={r['display_name']}")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
