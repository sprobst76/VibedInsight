"""Tests for the url_hash rehash CLI (A1.3/A1.4)."""

import csv
import hashlib
import io
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.database import async_session_maker
from app.models.content import ContentItem, ContentType, ProcessingStatus
from app.services.urlnorm import hash_url
from app.timeutils import utcnow
from app.tools.rehash import dup_hash, main, run_rehash


def _legacy_hash(tag: str) -> str:
    """Stand-in for a hash computed by the old (query-less) normalisation."""
    return hashlib.sha256(f"legacy:{tag}".encode()).hexdigest()


async def _seed(*items: dict) -> list[uuid.UUID]:
    ids = []
    async with async_session_maker() as db:
        for data in items:
            item = ContentItem(status=ProcessingStatus.COMPLETED, **data)
            db.add(item)
            await db.flush()
            ids.append(item.id)
        await db.commit()
    return ids


async def _hashes(ids: list[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    async with async_session_maker() as db:
        rows = await db.execute(
            select(ContentItem.id, ContentItem.url_hash).where(ContentItem.id.in_(ids))
        )
        return dict(rows.all())


@pytest.fixture
async def fixture_items(apply_migrations):
    """
    A (oldest) and B collide after rehash (utm parameter vs. fragment), C is
    already on the new hash, N is a note without URL. Timestamps are naive.
    """
    host = f"rehash-{uuid.uuid4().hex[:8]}.example"
    now = utcnow()
    assert now.tzinfo is None
    url_c = f"https://{host}/c?v=1"
    ids = await _seed(
        {
            "url": f"https://{host}/a?utm_source=newsletter",
            "url_hash": _legacy_hash(f"{host}-a"),
            "created_at": now - timedelta(days=2),
        },
        {
            "url": f"https://{host}/a#comments",
            "url_hash": _legacy_hash(f"{host}-b"),
            "created_at": now - timedelta(days=1),
        },
        {"url": url_c, "url_hash": hash_url(url_c), "created_at": now},
        {"content_type": ContentType.NOTE, "url": None, "url_hash": None, "created_at": now},
    )
    return dict(zip("ABCN", ids, strict=True)), f"https://{host}/a"


async def test_dry_run_writes_nothing_and_reports_collision(fixture_items):
    ids, canonical_url = fixture_items
    before = await _hashes(list(ids.values()))

    out = io.StringIO()
    plan = await run_rehash(apply=False, out=out)

    assert await _hashes(list(ids.values())) == before
    group = next(g for g in plan.collisions if g[0].new_hash == hash_url(canonical_url))
    assert [r.id for r in group] == [ids["A"], ids["B"]]
    assert str(ids["B"]) in out.getvalue()
    assert "DRY-RUN" in out.getvalue()


async def test_apply_keeps_all_items_and_is_idempotent(fixture_items, tmp_path):
    ids, canonical_url = fixture_items
    new_hash = hash_url(canonical_url)
    report = tmp_path / "rehash.csv"

    await run_rehash(apply=True, report_path=str(report), out=io.StringIO())

    after = await _hashes(list(ids.values()))
    assert set(after) == set(ids.values())  # nothing deleted
    assert after[ids["A"]] == new_hash
    assert after[ids["B"]] == dup_hash(new_hash, ids["B"])
    assert len(after[ids["B"]]) == 64
    assert after[ids["B"]].startswith(new_hash[:23] + ":dup:")
    assert after[ids["C"]] == hash_url(f"{canonical_url[:-2]}/c?v=1")
    assert after[ids["N"]] is None
    assert list(after.values()).count(new_hash) == 1

    rows = {r["id"]: r for r in csv.DictReader(report.open())}
    assert rows[str(ids["A"])]["action"] == "rehash"
    assert rows[str(ids["B"])]["action"] == "dup"
    assert rows[str(ids["B"])]["new_hash"] == new_hash
    assert rows[str(ids["C"])]["action"] == "unchanged"
    assert str(ids["N"]) not in rows

    second = await run_rehash(apply=True, out=io.StringIO())
    assert second.changes == []
    assert await _hashes(list(ids.values())) == after


async def test_apply_swaps_hash_from_younger_holder_to_oldest(apply_migrations):
    """Younger item already holds the new hash; the older one must take it over
    without tripping the unique index (two-phase update)."""
    host = f"rehash-{uuid.uuid4().hex[:8]}.example"
    url = f"https://{host}/watch?v=abc"
    new_hash = hash_url(url)
    old, young = await _seed(
        {
            "url": url + "&utm_medium=x",
            "url_hash": _legacy_hash(host),
            "created_at": datetime(2025, 1, 1, 12, 0),
        },
        {"url": url, "url_hash": new_hash, "created_at": datetime(2026, 1, 1, 12, 0)},
    )

    await run_rehash(apply=True, out=io.StringIO())

    after = await _hashes([old, young])
    assert after[old] == new_hash
    assert after[young] == dup_hash(new_hash, young)


async def test_cli_defaults_to_dry_run(fixture_items, capsys):
    ids, _ = fixture_items
    before = await _hashes(list(ids.values()))
    # main() calls asyncio.run, which cannot nest inside the test loop; run
    # it in a worker thread with its own loop.
    import asyncio

    from app.database import engine

    await engine.dispose()  # don't hand this loop's connections to the thread
    assert await asyncio.to_thread(main, []) == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert await _hashes(list(ids.values())) == before
