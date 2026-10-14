"""Tests for the processing pipeline: topic races, failure bookkeeping, retry tick."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from app.database import async_session_maker
from app.main import app
from app.models.content import ContentItem, ContentType, ProcessingStatus, Topic
from app.services import processing, scheduler
from app.services.fetcher import FetchStatusError


@pytest.fixture(autouse=True)
def _migrated(apply_migrations):
    pass


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace Ollama calls and the best-effort embedding step."""

    async def fake_summary(text, context=""):
        return "summary"

    async def fake_topics(text, context=""):
        return ["race-topic-" + RACE_SUFFIX[0], "other"]

    async def fake_embed(item, db):
        return None

    monkeypatch.setattr(processing, "generate_summary", fake_summary)
    monkeypatch.setattr(processing, "extract_topics", fake_topics)
    monkeypatch.setattr(processing, "_embed_and_relate", fake_embed)


RACE_SUFFIX = [""]


async def _make_item(**kwargs) -> uuid.UUID:
    async with async_session_maker() as db:
        item = ContentItem(
            content_type=kwargs.pop("content_type", ContentType.NOTE),
            status=kwargs.pop("status", ProcessingStatus.PENDING),
            ref_count=1,
            **kwargs,
        )
        db.add(item)
        await db.commit()
        return item.id


async def _get(item_id: uuid.UUID) -> ContentItem:
    async with async_session_maker() as db:
        result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
        return result.scalar_one()


async def test_concurrent_processing_with_same_new_topic(fake_llm):
    RACE_SUFFIX[0] = uuid.uuid4().hex[:8]
    ids = [await _make_item(title=f"n{i}", raw_text="some text") for i in range(4)]

    await asyncio.gather(*(processing.process_item(i) for i in ids))

    for i in ids:
        assert (await _get(i)).status == ProcessingStatus.COMPLETED
    async with async_session_maker() as db:
        result = await db.execute(select(Topic).where(Topic.name == f"race-topic-{RACE_SUFFIX[0]}"))
        assert len(result.scalars().all()) == 1


# ---------------------------------------------------------------------------
# Retry tick / backoff / manual retry
# ---------------------------------------------------------------------------


def test_backoff_doubles_and_is_capped():
    assert processing.retry_backoff(0) == timedelta(minutes=5)
    assert processing.retry_backoff(1) == timedelta(minutes=10)
    assert processing.retry_backoff(3) == timedelta(minutes=40)
    assert processing.retry_backoff(20) == timedelta(hours=12)


@pytest.fixture
async def clean_retry_queue(monkeypatch):
    """No leftover due FAILED items from other tests; capture scheduling."""
    async with async_session_maker() as db:
        await db.execute(
            update(ContentItem)
            .where(ContentItem.status == ProcessingStatus.FAILED)
            .values(next_retry_at=None)
        )
        await db.commit()
    scheduled: list = []
    monkeypatch.setattr(processing, "schedule_processing", scheduled.append)
    return scheduled


async def _failed_item(*, attempts=1, due_in=timedelta(minutes=-1), **kwargs) -> uuid.UUID:
    return await _make_item(
        content_type=ContentType.LINK,
        status=ProcessingStatus.FAILED,
        title="failed",
        url=f"https://example.com/{uuid.uuid4().hex}",
        attempts=attempts,
        last_error="boom",
        next_retry_at=datetime.now(UTC) + due_in,
        **kwargs,
    )


async def test_retry_tick_picks_only_due_items_below_attempt_limit(clean_retry_queue):
    due = await _failed_item()
    not_due = await _failed_item(due_in=timedelta(hours=1))
    exhausted = await _failed_item(attempts=5)

    count = await scheduler.retry_tick()

    assert count == 1
    assert clean_retry_queue == [due]
    assert (await _get(due)).status == ProcessingStatus.PENDING
    assert (await _get(not_due)).status == ProcessingStatus.FAILED
    assert (await _get(exhausted)).status == ProcessingStatus.FAILED


async def test_retry_tick_respects_batch_limit(clean_retry_queue):
    ids = [await _failed_item(due_in=timedelta(days=-400 + i)) for i in range(5)]

    assert await scheduler.retry_tick() == 3
    assert clean_retry_queue == ids[:3]  # oldest due first


async def test_failed_retry_raises_attempts_and_backs_off(clean_retry_queue, monkeypatch):
    async def boom(url):
        raise FetchStatusError(503, url)

    monkeypatch.setattr(processing, "extract_from_url", boom)
    item_id = await _failed_item(attempts=2)  # no raw_text -> will re-fetch

    await scheduler.retry_tick()
    await processing.process_item(item_id)

    item = await _get(item_id)
    assert item.status == ProcessingStatus.FAILED
    assert item.attempts == 3
    wait = item.next_retry_at - datetime.now(UTC)
    # backoff for 2 previous attempts: 5 min * 2^2 = 20 min
    assert timedelta(minutes=19) < wait <= timedelta(minutes=20)
    # not due again right away
    clean_retry_queue.clear()
    assert await scheduler.retry_tick() == 0


async def test_manual_retry_endpoint_resets_counter(clean_retry_queue, monkeypatch):
    scheduled: list = []
    monkeypatch.setattr("app.routers.user_items.schedule_processing", scheduled.append)
    item_id = await _failed_item(attempts=5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # link to the owner via the ingest-independent path: create a UserItem
        from app.dependencies import get_or_create_owner
        from app.models.user import UserItem

        async with async_session_maker() as db:
            owner = await get_or_create_owner(db)
            ui = UserItem(user_id=owner.id, content_id=item_id)
            db.add(ui)
            await db.commit()
            ui_id = ui.id

        resp = await client.post(f"/items/{ui_id}/retry")
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"
        assert scheduled == [item_id]
        item = await _get(item_id)
        assert item.attempts == 0 and item.last_error is None and item.next_retry_at is None

        # not failed any more -> 409
        again = await client.post(f"/items/{ui_id}/retry")
        assert again.status_code == 409
        assert (await client.post("/items/99999999/retry")).status_code == 404
