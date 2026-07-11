"""
Migration bootstrap — run by the container entrypoint before the app starts.

Handles three database states:
1. Empty database           -> `alembic upgrade head` runs the full chain
2. Alembic-managed database -> `alembic upgrade head` applies what's missing
3. Legacy database without an alembic_version stamp (created by the old
   init_db()/create_all path) -> stamp it at 004_rating (the schema state
   that path produced), then upgrade

Usage: python -m app.migrate
"""

import asyncio
import logging
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from alembic import command

logger = logging.getLogger(__name__)

# Schema state the legacy create_all + ad-hoc-ALTER path produced
LEGACY_REVISION = "004_rating"


async def _inspect_db() -> tuple[bool, bool]:
    """Return (has_alembic_version, has_user_items)."""
    from app.database import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name IN ('alembic_version', 'user_items')"
            )
        )
        tables = {row[0] for row in result.fetchall()}
    await engine.dispose()

    return "alembic_version" in tables, "user_items" in tables


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    has_stamp, has_legacy_tables = asyncio.run(_inspect_db())

    if not has_stamp and has_legacy_tables:
        logger.info(
            f"Legacy database without alembic stamp detected — stamping {LEGACY_REVISION}"
        )
        command.stamp(alembic_cfg, LEGACY_REVISION)

    logger.info("Running alembic upgrade head")
    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations complete")


if __name__ == "__main__":
    main()
