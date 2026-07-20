"""Tests for the serendipity resurfacing endpoint."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import async_session_maker
from app.dependencies import get_or_create_owner
from app.main import app
from app.models.content import ContentItem, ProcessingStatus
from app.models.user import UserItem
from app.timeutils import utcnow


@pytest.fixture
async def client(apply_migrations):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _seed_old_unread(db, *, title: str, days: int = 90) -> int:
    owner = await get_or_create_owner(db)
    old = utcnow() - timedelta(days=days)
    item = ContentItem(
        title=title,
        summary="Ein alter Fund.",
        status=ProcessingStatus.COMPLETED,
        created_at=old,
    )
    db.add(item)
    await db.flush()
    ui = UserItem(
        user_id=owner.id, content_id=item.id, is_read=False, created_at=old
    )
    db.add(ui)
    await db.commit()
    return ui.id


async def test_resurface_returns_an_old_unread_item(client):
    async with async_session_maker() as db:
        await _seed_old_unread(db, title="Wiederentdeckt-Test")

    response = await client.get("/resurface")
    assert response.status_code == 200
    item = response.json()["item"]
    assert item is not None
    assert item["is_read"] is False
    assert item["is_archived"] is False


async def test_resurface_null_when_disabled(client, monkeypatch):
    async with async_session_maker() as db:
        await _seed_old_unread(db, title="Egal-disabled")

    monkeypatch.setattr(settings, "resurfacing_enabled", False)

    response = await client.get("/resurface")
    assert response.status_code == 200
    assert response.json()["item"] is None


async def test_resurface_null_when_nothing_old_enough(client, monkeypatch):
    async with async_session_maker() as db:
        await _seed_old_unread(db, title="Nicht-alt-genug")

    # Require an age larger than any item (but within date range) so nothing qualifies.
    monkeypatch.setattr(settings, "resurfacing_min_age_days", 100_000)

    response = await client.get("/resurface")
    assert response.status_code == 200
    assert response.json()["item"] is None
