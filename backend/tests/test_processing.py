"""Tests for the processing pipeline: topic races, failure bookkeeping, retry tick."""

import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.database import async_session_maker
from app.models.content import ContentItem, ContentType, ProcessingStatus, Topic
from app.services import processing


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
