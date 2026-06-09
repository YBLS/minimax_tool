"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, ensure_dirs, get_settings
from app.crypto import warn_if_unbacked
from app.database import Database
from app.models import init_schema
from app.routers import configs, generate, health, history, media, secrets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("minimax")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    warn_if_unbacked()
    await init_schema()
    logger.info("Schema ready, serving on %s:%s", get_settings().host, get_settings().port)
    yield
    await Database.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="MiniMax Tool",
        description="Local web UI to call MiniMax APIs (image/voice/music/video)",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    app.include_router(health.router)
    app.include_router(configs.router)
    app.include_router(generate.router)
    app.include_router(history.router)
    app.include_router(secrets.router)
    app.include_router(media.router)

    # Serve frontend build output
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        # Mount assets directory for hashed bundles
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        # Catch-all: return index.html for any non-API path.
        from fastapi.responses import FileResponse

        @app.get("/", include_in_schema=False)
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str = ""):
            if full_path.startswith("api/"):
                from fastapi import HTTPException
                raise HTTPException(404, "Not found")
            resp = FileResponse(str(STATIC_DIR / "index.html"))
            # HTML references content-hashed JS/CSS by filename; if we let the
            # browser cache this, users get stuck on a stale bundle reference
            # after a rebuild. Force revalidation every time.
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp

        logger.info("Serving static frontend from %s", STATIC_DIR)
    else:
        logger.warning(
            "No frontend build at %s — only API endpoints are available. "
            "Run `npm run build` in ./frontend, or open the docs at /docs.",
            STATIC_DIR,
        )

    return app


app = create_app()
