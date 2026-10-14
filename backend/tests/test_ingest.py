"""Ingest tests: duplicate-URL races, async 202 flow, failures, private hosts."""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import settings
from app.database import async_session_maker
from app.main import app
from app.models.content import ContentItem, ProcessingStatus
from app.models.user import UserItem
from app.services import processing
from app.services.fetcher import FetchStatusError


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
            await db.execute(
                select(func.count()).select_from(ContentItem).where(ContentItem.url == url)
            )
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


async def _db_item(url: str) -> ContentItem:
    async with async_session_maker() as db:
        return (await db.execute(select(ContentItem).where(ContentItem.url == url))).scalar_one()


async def test_ingest_url_returns_202_with_pending_item(client, scheduled):
    url = _unique_url()

    resp = await client.post("/ingest/url", json={"url": url})

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["title"] == url
    assert body["attempts"] == 0
    assert body["last_error"] is None
    assert body["url"] == url
    assert len(scheduled) == 1
    # the item is immediately visible via the normal item endpoint
    got = await client.get(f"/items/{body['id']}")
    assert got.status_code == 200


async def test_duplicate_url_returns_200_without_new_processing(client, scheduled):
    url = _unique_url()
    first = await client.post("/ingest/url", json={"url": url})
    second = await client.post("/ingest/url", json={"url": url})

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(scheduled) == 1
    assert await _count_items(url) == (1, 1)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/admin", "http://localhost:8000/x", "http://192.168.1.5/", "http://[::1]/"],
)
async def test_private_host_rejected_before_item_is_created(client, scheduled, url, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_urls", False)
    url = f"{url}?t={uuid.uuid4().hex}"
    resp = await client.post("/ingest/url", json={"url": url})

    assert resp.status_code == 400
    assert scheduled == []
    assert await _count_items(url) == (0, 0)


async def test_concurrent_ingest_same_url_creates_one_item(client, scheduled):
    url = _unique_url()

    r1, r2, r3 = await asyncio.gather(
        *(client.post("/ingest/url", json={"url": url}) for _ in range(3))
    )

    codes = sorted(r.status_code for r in (r1, r2, r3))
    assert codes[0] in (200, 202) and codes[-1] in (200, 202)
    assert codes.count(202) == 1
    assert r1.json()["id"] == r2.json()["id"] == r3.json()["id"]
    assert await _count_items(url) == (1, 1)
    assert len(scheduled) == 1


async def test_fetch_error_marks_item_failed_and_keeps_it(client, scheduled, monkeypatch):
    async def boom(url):
        raise FetchStatusError(404, url)

    monkeypatch.setattr("app.services.processing.extract_from_url", boom)
    url = _unique_url()
    resp = await client.post("/ingest/url", json={"url": url})
    item_id = scheduled[0]

    await processing.process_item(item_id)

    item = await _db_item(url)
    assert item.status == ProcessingStatus.FAILED
    assert item.attempts == 1
    assert item.last_error and "404" in item.last_error and len(item.last_error) <= 300
    assert item.next_retry_at is not None
    # the user item survives and is still reachable
    got = await client.get(f"/items/{resp.json()['id']}")
    assert got.status_code == 200
    assert got.json()["status"] == "failed"
    assert got.json()["attempts"] == 1
    assert "404" in got.json()["last_error"]


async def test_successful_async_fetch_fills_title_and_completes(client, scheduled, monkeypatch):
    async def ok(url):
        return {"title": "Real Title", "text": "body text", "source": "example.com"}

    async def fake_summary(text, context=""):
        return "sum"

    async def fake_topics(text, context=""):
        return ["thema"]

    async def noop(item, db):
        return None

    monkeypatch.setattr("app.services.processing.extract_from_url", ok)
    monkeypatch.setattr(processing, "generate_summary", fake_summary)
    monkeypatch.setattr(processing, "extract_topics", fake_topics)
    monkeypatch.setattr(processing, "_embed_and_relate", noop)
    url = _unique_url()
    await client.post("/ingest/url", json={"url": url})

    await processing.process_item(scheduled[0])

    item = await _db_item(url)
    assert item.status == ProcessingStatus.COMPLETED
    assert item.title == "Real Title"
    assert item.raw_text == "body text"


async def test_bulk_routes_still_match_before_item_id(client):
    # /items/bulk/* must not be swallowed by /items/{item_id}/... (would be 422)
    resp = await client.post("/items/bulk/read", json={"ids": []})
    assert resp.status_code == 200
    resp = await client.post("/items/bulk/archive", json={"ids": []})
    assert resp.status_code == 200
    resp = await client.post("/items/bulk/delete", json={"ids": []})
    assert resp.status_code == 200
