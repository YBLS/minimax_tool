"""Dev entry: `uv run python main.py` from backend/."""

from __future__ import annotations

import uvicorn

from app.config import get_settings


if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host,
        port=s.port,
        reload=s.debug,
        log_level="info",
    )
