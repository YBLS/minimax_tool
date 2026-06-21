"""FastAPI application factory."""

from __future__ import annotations

import logging
import base64
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, ensure_dirs, get_settings
from app.crypto import warn_if_unbacked
from app.database import Database
from app.models import init_schema
from app.routers import configs, generate, health, history, key_providers, media, secrets, translate

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
    from app.database import execute
    await execute(
        "UPDATE generation_history SET status='failed', "
        "error_message='Interrupted by application restart' "
        "WHERE status IN ('running', 'pending')"
    )
    logger.info("Schema ready, serving on %s:%s", get_settings().host, get_settings().port)
    yield
    await Database.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MiniMax Tool",
        description="Local web UI to call MiniMax APIs (image/voice/music/video)",
        version="0.2.0",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=True,
        )

    @app.middleware("http")
    async def production_security(request, call_next):
        if settings.app_username and request.url.path != "/api/health":
            supplied = request.headers.get("authorization", "")
            expected = base64.b64encode(
                f"{settings.app_username}:{settings.app_password}".encode()
            ).decode()
            if not hmac.compare_digest(supplied, f"Basic {expected}"):
                return JSONResponse(
                    {"detail": "Authentication required"}, status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="MiniMax Tool"'},
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob: https:; "
            "media-src 'self' blob: https:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'"
        )
        return response

    app.include_router(health.router)
    app.include_router(configs.router)
    app.include_router(key_providers.router)
    app.include_router(generate.router)
    app.include_router(history.router)
    app.include_router(secrets.router)
    app.include_router(media.router)
    app.include_router(translate.router)

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
