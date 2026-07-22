"""
Audio-Digest router: turn a weekly summary into spoken audio.

MVP scope — reuses the *existing* weekly-summary text (no extra LLM call), so
the only new cost is TTS, which is cheap (see app.services.audio). The audio is
cached on disk keyed by the summary's `generated_at`, so a given digest is
synthesized at most once. A later slice adds a purpose-written "podcast" script
(two-host dialogue) and app-side playback + drill-down into the RAG chat.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.content import WeeklySummary
from app.models.user import User
from app.services import audio

logger = logging.getLogger(__name__)

router = APIRouter()


def build_digest_script(summary: WeeklySummary) -> str:
    """Compose a natural German spoken text from an existing weekly summary."""
    parts: list[str] = ["Willkommen zu deinem Wochenrückblick."]

    if summary.tldr:
        parts.append(summary.tldr)

    if summary.summary:
        parts.append("Im Detail.")
        parts.append(summary.summary)

    insights = json.loads(summary.key_insights) if summary.key_insights else []
    if insights:
        parts.append("Die wichtigsten Erkenntnisse.")
        parts.extend(f"{i}. {text}" for i, text in enumerate(insights, start=1))

    parts.append("Das war dein Wochenrückblick.")
    return "\n".join(p.strip() for p in parts if p and p.strip())


def _cache_path(summary: WeeklySummary, ext: str) -> Path:
    stamp = int(summary.generated_at.timestamp()) if summary.generated_at else 0
    name = f"weekly_{summary.id}_{stamp}_{settings.tts_voice}.{ext}"
    return Path(settings.audio_cache_dir) / name


@router.get("/status")
async def audio_status(user: User = Depends(get_current_user)):
    """Report whether TTS is usable — lets the app hide the play button."""
    return {"available": audio.is_available(), "voice": settings.tts_voice}


@router.get("/weekly/{summary_id}")
async def weekly_audio(
    summary_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the weekly digest as audio (MP3 when ffmpeg is present, else WAV)."""
    if not audio.is_available():
        raise HTTPException(status_code=503, detail="Audio synthesis is not available")

    summary = await db.get(WeeklySummary, summary_id)
    if not summary or summary.user_id != user.id:
        raise HTTPException(status_code=404, detail="Weekly summary not found")

    script = build_digest_script(summary)
    if not script or not (summary.tldr or summary.summary):
        raise HTTPException(status_code=400, detail="Summary has no text to narrate")

    ext = "mp3" if settings.audio_format == "mp3" else "wav"
    cache = _cache_path(summary, ext)
    media = "audio/mpeg" if ext == "mp3" else "audio/wav"

    if cache.exists():
        data = cache.read_bytes()
    else:
        data, media = audio.synthesize(script)
        ext = "mp3" if media == "audio/mpeg" else "wav"
        cache = _cache_path(summary, ext)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
        except OSError as e:
            logger.warning("Could not cache audio at %s: %s", cache, e)

    return Response(content=data, media_type=media)
