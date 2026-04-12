from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_transcripts import router as transcripts_router
from app.api.routes_uploads import router as uploads_router
from app.api.routes_edits import router as edits_router
from app.api.routes_retakes import router as retakes_router
from app.api.routes_auth import router as auth_router
from app.core.config import settings
from app.services.ffmpeg_service import log_ffmpeg_startup_status


def _configure_app_logging() -> None:
    """Ensure pipeline logs are visible even when uvicorn --log-level is warning."""
    log = logging.getLogger("app")
    if log.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"),
    )
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    log_ffmpeg_startup_status()
    yield


def create_app() -> FastAPI:
    _configure_app_logging()
    app = FastAPI(
        title="Shotcut AI - Video Editor Backend",
        version="0.1.0",
        lifespan=_app_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.api_cors_allow_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(uploads_router)
    app.include_router(transcripts_router)
    app.include_router(edits_router)
    app.include_router(retakes_router)
    app.include_router(auth_router)

    return app


app = create_app()

