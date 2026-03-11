"""FastAPI application entry point for instagram_service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.posts import router as posts_router, _scheduler as post_scheduler
from app.routes.viral import router as viral_router, _scheduler as viral_scheduler

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    settings = get_settings()
    logger.info("instagram_service starting up (debug=%s)", settings.debug)
    post_scheduler.start()
    viral_scheduler.start()
    try:
        yield
    finally:
        post_scheduler.shutdown()
        viral_scheduler.shutdown()
        logger.info("instagram_service shut down")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured :class:`fastapi.FastAPI` instance.
    """
    app = FastAPI(
        title="Instagram Service",
        description=(
            "Microservice for automated Instagram content generation and "
            "publishing for e-commerce product curation."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(posts_router)
    app.include_router(viral_router)

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["health"], summary="Health check")
    async def health() -> dict:
        """Return service liveness status."""
        return {"status": "ok", "service": "instagram_service"}

    return app


app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
