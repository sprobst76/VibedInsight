import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def _run_alembic_upgrade() -> None:
    """Run Alembic migrations synchronously (called from thread executor)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Run all pending Alembic migrations on startup."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_alembic_upgrade)
