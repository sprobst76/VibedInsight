"""
Audio-Digest router: turn a weekly summary into spoken audio.

The digest is first rewritten into a spoken-word script by the LLM (P13.6) so
it sounds heard, not read, then normalized for the TTS voice and synthesized.
If the LLM call fails, it falls back to reading the plain digest text. The audio
is cached on disk keyed by the summary's `generated_at`, so a given digest is
synthesized (and scripted) at most once.
"""

import asyncio
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
from app.services.summarizer import generate_podcast_script

logger = logging.getLogger(__name__)

router = APIRouter()


def build_digest_script(summary: WeeklySummary) -> str:
    """Compose a plain spoken text from a weekly summary (LLM-free fallback)."""
    parts: list[str] = ["Willkommen zu deinem Wochenrückblick."]

    if summary.tldr:
        parts.append(summary.tldr)

    if summary.summary:
        parts.append("Im Detail.")
        parts.append(summary.summary)

    insights = json.loads(summary.key_insights) if summary.key_insights else []
    if insights:
        parts.append("Die wichtigsten Erkenntnisse.")
        parts.extend(str(text) for text in insights)

    parts.append("Das war dein Wochenrückblick.")
    return "\n".join(p.strip() for p in parts if p and p.strip())


def _digest_source_text(summary: WeeklySummary) -> str:
    """The raw digest content fed to the podcast-script LLM prompt."""
    parts: list[str] = []
    if summary.tldr:
        parts.append(summary.tldr)
    if summary.summary:
        parts.append(summary.summary)
    insights = json.loads(summary.key_insights) if summary.key_insights else []
    if insights:
        parts.append("Erkenntnisse: " + "; ".join(str(t) for t in insights))
    topics = json.loads(summary.top_topics) if summary.top_topics else []
    if topics:
        parts.append("Themen: " + ", ".join(str(t) for t in topics))
    return "\n".join(parts)


async def _build_spoken_script(summary: WeeklySummary) -> str:
    """Spoken-word script for TTS: LLM podcast script, plain digest as fallback."""
    if settings.audio_podcast_script:
        try:
            script = await generate_podcast_script(_digest_source_text(summary))
            if script and script.strip():
                return script
            logger.warning("Podcast script was empty; falling back to plain digest")
        except Exception as e:
            logger.warning("Podcast script generation failed (%s); using plain digest", e)
    return build_digest_script(summary)


# Bump when the script prompt or speech normalization changes, so cached audio
# is regenerated instead of serving an older rendering.
_SPEECH_CACHE_VERSION = "2"


def _cache_path(summary: WeeklySummary, ext: str) -> Path:
    stamp = int(summary.generated_at.timestamp()) if summary.generated_at else 0
    # Include the script mode and speech version so a mode switch or a
    # normalization change doesn't serve stale audio.
    mode = "pod" if settings.audio_podcast_script else "plain"
    name = (
        f"weekly_{summary.id}_{stamp}_{settings.tts_voice}"
        f"_{mode}_v{_SPEECH_CACHE_VERSION}.{ext}"
    )
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

    if not (summary.tldr or summary.summary):
        raise HTTPException(status_code=400, detail="Summary has no text to narrate")

    ext = "mp3" if settings.audio_format == "mp3" else "wav"
    cache = _cache_path(summary, ext)
    media = "audio/mpeg" if ext == "mp3" else "wav"

    if cache.exists():
        data = cache.read_bytes()
    else:
        script = audio.normalize_for_speech(await _build_spoken_script(summary))
        # Piper synthesis is blocking CPU work — keep it off the event loop.
        data, media = await asyncio.to_thread(audio.synthesize, script)
        ext = "mp3" if media == "audio/mpeg" else "wav"
        cache = _cache_path(summary, ext)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
        except OSError as e:
            logger.warning("Could not cache audio at %s: %s", cache, e)

    return Response(content=data, media_type=media)
