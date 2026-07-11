"""
In-process scheduler: generates the weekly digest every Sunday at 18:00
(server time) so it's ready when the week ends — no external cron needed.

Deliberately simple: a single asyncio loop task started from the app
lifespan. If the server is down at the scheduled moment, the digest is
generated on the next Sunday or on demand via the API.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.config import settings
from app.database import async_session_maker
from app.dependencies import get_or_create_owner

logger = logging.getLogger(__name__)

WEEKLY_DAY = 6  # Sunday (Monday=0)
WEEKLY_HOUR = 18


def _seconds_until_next_run(now: datetime) -> float:
    days_ahead = (WEEKLY_DAY - now.weekday()) % 7
    run_at = (now + timedelta(days=days_ahead)).replace(
        hour=WEEKLY_HOUR, minute=0, second=0, microsecond=0
    )
    if run_at <= now:
        run_at += timedelta(days=7)
    return (run_at - now).total_seconds()


async def weekly_digest_loop() -> None:
    """Sleep until Sunday evening, generate the digest, repeat."""
    while True:
        wait = _seconds_until_next_run(datetime.now())
        logger.info(f"Weekly digest scheduler: next run in {wait / 3600:.1f}h")
        await asyncio.sleep(wait)

        try:
            await generate_weekly_digest()
        except Exception:
            logger.exception("Scheduled weekly digest generation failed")


async def generate_weekly_digest() -> None:
    """Generate the current week's digest for the owner."""
    # Imported here to avoid a circular import (weekly router imports services)
    from app.routers.weekly import NoItemsError, generate_summary_for, get_or_create_week_summary

    async with async_session_maker() as db:
        user = await get_or_create_owner(db)
        summary = await get_or_create_week_summary(user, db)
        try:
            await generate_summary_for(summary, user, db)
            logger.info(f"Weekly digest generated for week {summary.week_start.date()}")
        except NoItemsError:
            logger.info("Weekly digest skipped: no items this week")


def start_scheduler() -> asyncio.Task | None:
    """Start the digest loop if enabled; returns the task for lifecycle handling."""
    if not settings.weekly_auto_generate:
        logger.info("Weekly digest scheduler disabled (WEEKLY_AUTO_GENERATE=false)")
        return None
    return asyncio.create_task(weekly_digest_loop())
