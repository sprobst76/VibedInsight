"""Tests for KI-Triage scoring."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import async_session_maker
from app.dependencies import get_or_create_owner
from app.main import app
from app.models.content import ContentEmbedding, ContentItem, ProcessingStatus
from app.models.user import UserItem


@pytest.fixture
async def client(apply_migrations):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _vec(i: int) -> list[float]:
    v = [0.0] * 1024
    v[i] = 1.0
    return v


async def _add(db, owner, *, title, vec_index, rating=0):
    item = ContentItem(title=title, status=ProcessingStatus.COMPLETED)
    db.add(item)
    await db.flush()
    db.add(ContentEmbedding(content_id=item.id, embedding=_vec(vec_index)))
    ui = UserItem(user_id=owner.id, content_id=item.id, rating=rating)
    db.add(ui)
    return item, ui


async def test_retriage_scores_similar_high_and_dissimilar_low(client):
    async with async_session_maker() as db:
        owner = await get_or_create_owner(db)
        loved, _ = await _add(db, owner, title="Loved", vec_index=0, rating=5)
        _, ui_sim = await _add(db, owner, title="Similar", vec_index=0)
        _, ui_dis = await _add(db, owner, title="Different", vec_index=1)
        await db.commit()
        sim_id, dis_id = ui_sim.id, ui_dis.id
        loved_id = loved.id

    resp = await client.post("/admin/retriage")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 3

    sim = (await client.get(f"/items/{sim_id}")).json()
    dis = (await client.get(f"/items/{dis_id}")).json()
    assert sim["triage_score"] >= 0.99  # shares the vector of a 5-star item
    assert dis["triage_score"] is not None and dis["triage_score"] < 0.5

    # Clean up (identical vectors would otherwise leak into other suites).
    async with async_session_maker() as db:
        await db.execute(delete(ContentItem).where(ContentItem.id == loved_id))
        for uid in (sim_id, dis_id):
            ui = await db.get(UserItem, uid)
            if ui:
                await db.execute(
                    delete(ContentItem).where(ContentItem.id == ui.content_id)
                )
        await db.commit()


async def test_items_accepts_triage_sort(client):
    resp = await client.get("/items", params={"sort_by": "triage"})
    assert resp.status_code == 200
    assert "items" in resp.json()
