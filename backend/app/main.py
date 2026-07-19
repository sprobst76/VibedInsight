import logging
import secrets
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import admin, export, ingest, topics, user_items, weekly
from app.services.processing import requeue_stuck_items
from app.services.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

APP_VERSION = "0.4.1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic in production (entrypoint runs
    # `alembic upgrade head`); init_db only creates missing tables on
    # fresh dev/test databases.
    await init_db()

    if not settings.api_key:
        logger.warning(
            "API_KEY is not set — the API is UNPROTECTED. "
            "Set API_KEY in .env for any non-local deployment."
        )

    await requeue_stuck_items()
    scheduler_task = start_scheduler()

    yield

    if scheduler_task:
        scheduler_task.cancel()


app = FastAPI(
    title="VibedInsight API",
    description="Personal knowledge platform - collect, analyze, and summarize content",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS for Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths reachable without the API key
PUBLIC_PATHS = {"/health"}


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Require X-API-Key on every request when API_KEY is configured."""
    if settings.api_key and request.url.path not in PUBLIC_PATHS and request.method != "OPTIONS":
        provided = request.headers.get("x-api-key", "")
        if not secrets.compare_digest(provided, settings.api_key):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


# Include routers
app.include_router(user_items.router, prefix="/items", tags=["Items"])
app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
app.include_router(topics.router, prefix="/topics", tags=["Topics"])
app.include_router(weekly.router, prefix="/weekly", tags=["Weekly Summary"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(export.router, prefix="/export", tags=["Export"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": APP_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
