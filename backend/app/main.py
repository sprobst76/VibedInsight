from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, ingest, items, topics, user_items, vault, weekly


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="VibedInsight API",
    description="Personal knowledge platform - collect, analyze, and summarize content",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)  # Auth router has its own prefix
app.include_router(vault.router, prefix="/vault", tags=["Vault"])
# User items router at /items (for Flutter frontend compatibility)
app.include_router(user_items.router, prefix="/items", tags=["Items"])
# Content items router at /content (anonymous content operations)
app.include_router(items.router, prefix="/content", tags=["Content"])
app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
app.include_router(topics.router, prefix="/topics", tags=["Topics"])
app.include_router(weekly.router, prefix="/weekly", tags=["Weekly Summary"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
