"""Ingest tests: duplicate-URL races, async 202 flow, failures, private hosts."""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.database import async_session_maker
from app.main import app
from app.models.content import ContentItem
from app.models.user import UserItem


@pytest.fixture
async def client(apply_migrations):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def scheduled(monkeypatch):
    """Capture schedule_processing calls instead of running the pipeline."""
    calls: list = []
    monkeypatch.setattr("app.routers.ingest.schedule_processing", calls.append)
    return calls


def _unique_url() -> str:
    return f"https://example.com/article-{uuid.uuid4().hex}"


async def _count_items(url: str) -> tuple[int, int]:
    async with async_session_maker() as db:
        items = (
            await db.execute(select(func.count()).select_from(ContentItem).where(ContentItem.url == url))
        ).scalar_one()
        links = (
            await db.execute(
                select(func.count())
                .select_from(UserItem)
                .join(ContentItem, ContentItem.id == UserItem.content_id)
                .where(ContentItem.url == url)
            )
        ).scalar_one()
        return items, links


async def test_concurrent_ingest_same_url_creates_one_item(client, scheduled, monkeypatch):
    async def slow_extract(url):
        await asyncio.sleep(0.2)  # both requests pass the duplicate check first
        return {"title": "T", "text": "body", "source": "example.com"}

    monkeypatch.setattr("app.routers.ingest.extract_from_url", slow_extract)
    url = _unique_url()

    r1, r2 = await asyncio.gather(
        client.post("/ingest/url", json={"url": url}),
        client.post("/ingest/url", json={"url": url}),
    )

    assert r1.status_code < 300 and r2.status_code < 300
    assert r1.json()["id"] == r2.json()["id"]
    assert await _count_items(url) == (1, 1)
    assert len(scheduled) == 1
