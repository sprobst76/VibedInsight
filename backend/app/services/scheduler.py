"""
In-process scheduler: generates the weekly digest every Sunday at 18:00
(server time) so it's ready when the week ends — no external cron needed.

Also runs a retry tick every few minutes that re-processes FAILED items whose
backoff has elapsed (see retry_tick).

Deliberately simple: asyncio loop tasks started from the app lifespan. If the
server is down at the scheduled moment, the digest is generated on the next
Sunday or on demand via the API.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.database import async_session_maker
from app.dependencies import get_or_create_owner
from app.models.content import ContentItem, ProcessingStatus

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


async def retry_tick() -> int:
    """
    Re-process FAILED items that are due for an automatic retry.

    Picks up to `retry_batch_size` items with attempts < `retry_max_attempts`
    and next_retry_at <= now. FOR UPDATE SKIP LOCKED keeps overlapping ticks
    (or several workers) from taking the same item; the picked items are set
    to PENDING before the lock is released. Returns the number scheduled.
    """
    # Imported lazily so tests can patch processing.schedule_processing
    from app.services import processing

    async with async_session_maker() as db:
        result = await db.execute(
            select(ContentItem)
            .where(
                ContentItem.status == ProcessingStatus.FAILED,
                ContentItem.attempts < settings.retry_max_attempts,
                ContentItem.next_retry_at <= datetime.now(UTC),
            )
            .order_by(ContentItem.next_retry_at)
            .limit(settings.retry_batch_size)
            .with_for_update(skip_locked=True)
        )
        items = list(result.scalars().all())
        for item in items:
            item.status = ProcessingStatus.PENDING
        ids = [item.id for item in items]
        await db.commit()

    for item_id in ids:
        processing.schedule_processing(item_id)
    if ids:
        logger.info(f"Retry tick: rescheduled {len(ids)} failed item(s)")
    return len(ids)


async def retry_loop() -> None:
    """Run retry_tick periodically."""
    while True:
        await asyncio.sleep(settings.retry_tick_interval_seconds)
        try:
            await retry_tick()
        except Exception:
            logger.exception("Retry tick failed")


def start_scheduler() -> list[asyncio.Task]:
    """Start the enabled background loops; returns the tasks for lifecycle handling."""
    tasks: list[asyncio.Task] = []
    if settings.weekly_auto_generate:
        tasks.append(asyncio.create_task(weekly_digest_loop()))
    else:
        logger.info("Weekly digest scheduler disabled (WEEKLY_AUTO_GENERATE=false)")
    if settings.retry_tick_enabled:
        tasks.append(asyncio.create_task(retry_loop()))
    else:
        logger.info("Retry tick disabled (RETRY_TICK_ENABLED=false)")
    return tasks
