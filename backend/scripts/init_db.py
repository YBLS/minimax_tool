"""One-shot DB initializer (also runs on app startup, but this is the CLI)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the parent `app` package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crypto import warn_if_unbacked  # noqa: E402
from app.database import Database  # noqa: E402
from app.models import init_schema  # noqa: E402


async def main() -> None:
    warn_if_unbacked()
    await init_schema()
    print("Schema ready.")
    await Database.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
