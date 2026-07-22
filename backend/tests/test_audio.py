"""Tests for the Audio-Digest feature (Piper TTS)."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import async_session_maker
from app.dependencies import get_or_create_owner
from app.main import app
from app.models.content import WeeklySummary
from app.routers.audio import build_digest_script
from app.services import audio
from app.timeutils import utcnow

requires_tts = pytest.mark.skipif(
    not audio.is_available(),
    reason="Piper voice model not present (baked into Docker image only)",
)


@pytest.fixture
async def client(apply_migrations):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def test_build_digest_script_composes_all_parts():
    s = WeeklySummary(
        tldr="Kurzfassung der Woche.",
        summary="Ausführlicher Text.",
        key_insights=json.dumps(["Erste Erkenntnis", "Zweite Erkenntnis"]),
    )
    script = build_digest_script(s)
    assert "Willkommen zu deinem Wochenrückblick." in script
    assert "Kurzfassung der Woche." in script
    assert "Ausführlicher Text." in script
    assert "1. Erste Erkenntnis" in script
    assert "2. Zweite Erkenntnis" in script


def test_build_digest_script_handles_empty_fields():
    script = build_digest_script(WeeklySummary(tldr="Nur ein Satz."))
    assert "Nur ein Satz." in script
    assert "Die wichtigsten Erkenntnisse." not in script


async def test_audio_status(client):
    resp = await client.get("/audio/status")
    assert resp.status_code == 200
    assert "available" in resp.json()


async def test_weekly_audio_404_for_missing_summary(client):
    resp = await client.get("/audio/weekly/999999")
    # 503 when TTS is unavailable is checked before the lookup; otherwise 404.
    assert resp.status_code in (404, 503)


@requires_tts
def test_synthesize_wav_produces_riff():
    wav = audio.synthesize_wav("Dies ist ein kurzer Test.")
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert len(wav) > 1000


@requires_tts
async def test_weekly_audio_returns_audio(client):
    async with async_session_maker() as db:
        owner = await get_or_create_owner(db)
        summary = WeeklySummary(
            user_id=owner.id,
            week_start=utcnow(),
            week_end=utcnow(),
            tldr="Diese Woche ging es um selbst-gehostete Sprachmodelle.",
            summary="Lokale Modelle werden gut genug für den Alltag.",
            generated_at=utcnow(),
        )
        db.add(summary)
        await db.commit()
        summary_id = summary.id

    resp = await client.get(f"/audio/weekly/{summary_id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] in ("audio/mpeg", "audio/wav")
    assert len(resp.content) > 1000

    async with async_session_maker() as db:
        await db.execute(delete(WeeklySummary).where(WeeklySummary.id == summary_id))
        await db.commit()
