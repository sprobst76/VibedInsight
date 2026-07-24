"""Tests for async weekly-digest generation (kick off + poll status)."""

import asyncio
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import async_session_maker
from app.dependencies import get_or_create_owner
from app.main import app
from app.models.content import WeeklySummary
from app.timeutils import utcnow


@pytest.fixture
async def client(apply_migrations):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _poll_status(client, summary_id, *, tries=30, delay=0.2):
    for _ in range(tries):
        resp = await client.get(f"/weekly/{summary_id}/generation-status")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] != "processing":
            return body
        await asyncio.sleep(delay)
    raise AssertionError("generation stayed 'processing' too long")


async def test_generate_returns_processing_then_fails_for_empty_week(client):
    # A past week with no items -> generation raises NoItemsError (no LLM call),
    # which exercises the full async kickoff -> poll -> failed path.
    async with async_session_maker() as db:
        owner = await get_or_create_owner(db)
        past = utcnow() - timedelta(days=400)
        s = WeeklySummary(
            user_id=owner.id,
            week_start=past,
            week_end=past + timedelta(days=6),
            items_count=0,
            items_processed=0,
        )
        db.add(s)
        await db.commit()
        sid = s.id

    resp = await client.post(f"/weekly/{sid}/generate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "processing"
    assert body["summary_id"] == sid

    final = await _poll_status(client, sid)
    assert final["status"] == "failed"
    assert final["error"]


async def test_generation_status_idle_for_ungenerated_summary(client):
    async with async_session_maker() as db:
        owner = await get_or_create_owner(db)
        s = WeeklySummary(
            user_id=owner.id,
            week_start=utcnow(),
            week_end=utcnow(),
            items_count=0,
            items_processed=0,
        )
        db.add(s)
        await db.commit()
        sid = s.id

    resp = await client.get(f"/weekly/{sid}/generation-status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"


async def test_generation_status_completed_when_summary_present(client):
    async with async_session_maker() as db:
        owner = await get_or_create_owner(db)
        s = WeeklySummary(
            user_id=owner.id,
            week_start=utcnow(),
            week_end=utcnow(),
            items_count=1,
            items_processed=1,
            summary="Fertiger Digest-Text.",
        )
        db.add(s)
        await db.commit()
        sid = s.id

    resp = await client.get(f"/weekly/{sid}/generation-status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_generation_status_404_for_missing(client):
    resp = await client.get("/weekly/999999/generation-status")
    assert resp.status_code == 404
