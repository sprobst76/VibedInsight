"""
Text-to-speech for the Audio-Digest feature ("Höre deinen Wochenrückblick").

Uses Piper (https://github.com/OHF-Voice/piper1-gpl) — a small, CPU-friendly
neural TTS. A benchmark on a 4-core box synthesizes ~59 s of German speech in
~2 s (real-time factor ~0.03), so synthesis is NOT the bottleneck the way the
RAG prompt-eval is; it runs comfortably on the CPU-only VPS and the result is
cached, so it happens at most once per digest.

The Piper voice model (~61 MB) is NOT in git — it is baked into the Docker
image at build time (see Dockerfile) into `tts_voices_dir`. For local dev,
point `TTS_VOICES_DIR` at a directory holding `<voice>.onnx` + `.onnx.json`
(download via `python -m piper.download_voices <voice> --data-dir <dir>`).
When the voice or the piper package is missing, `is_available()` is False and
the audio endpoints degrade to 503 instead of crashing.
"""

import io
import logging
import re
import shutil
import subprocess
import time
import wave
from functools import lru_cache
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Abbreviations the small TTS voice reads letter-by-letter or wrong — expanded
# before synthesis so they are spoken as words.
_ABBREVIATIONS = {
    r"\bz\.\s?B\.": "zum Beispiel",
    r"\bu\.\s?a\.": "unter anderem",
    r"\bd\.\s?h\.": "das heißt",
    r"\bu\.\s?U\.": "unter Umständen",
    r"\bbzw\.": "beziehungsweise",
    r"\busw\.": "und so weiter",
    r"\betc\.": "und so weiter",
    r"\bca\.": "circa",
    r"\bNr\.": "Nummer",
    r"\bAI\b": "künstliche Intelligenz",
}

# Proper names the German voice mispronounces — respelled phonetically.
# Applied case-insensitively (the replacement carries the intended casing).
_PRONUNCIATIONS = {
    r"\bClaude\b": "Kload",
}


def normalize_for_speech(text: str) -> str:
    """Clean text so the TTS voice reads it naturally.

    Strips URLs and markdown, drops list markers, and expands common
    abbreviations. Applied to whatever text goes to synthesis (LLM podcast
    script or the plain digest fallback).
    """
    # Strip URLs (spoken URLs are noise).
    text = re.sub(r"https?://\S+|\bwww\.\S+", "", text)
    # Remove markdown emphasis / code / heading markers.
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [label](url) -> label
    # Drop leading list markers ("- ", "* ", "1. ") per line.
    text = re.sub(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+", "", text)
    # Expand abbreviations.
    for pattern, repl in _ABBREVIATIONS.items():
        text = re.sub(pattern, repl, text)
    # Respell mispronounced names.
    for pattern, repl in _PRONUNCIATIONS.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    # Collapse whitespace but keep sentence breaks as newlines.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _voice_paths() -> tuple[Path, Path]:
    base = Path(settings.tts_voices_dir) / settings.tts_voice
    return base.with_suffix(".onnx"), base.with_suffix(".onnx.json")


def is_available() -> bool:
    """True when Piper is importable and the configured voice model exists."""
    if not settings.audio_enabled:
        return False
    try:
        import piper  # noqa: F401
    except ImportError:
        return False
    onnx, cfg = _voice_paths()
    return onnx.exists() and cfg.exists()


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


@lru_cache(maxsize=1)
def _load_voice():
    """Load the Piper voice once (the 61 MB model init is not free)."""
    from piper import PiperVoice

    onnx, cfg = _voice_paths()
    logger.info("Loading Piper voice %s", onnx)
    return PiperVoice.load(str(onnx), str(cfg))


def synthesize_wav(text: str) -> bytes:
    """Synthesize `text` to WAV bytes (mono 16-bit). Raises if unavailable."""
    if not is_available():
        raise RuntimeError("TTS is not available (piper or voice model missing)")
    voice = _load_voice()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize_wav(text, wf)
    return buf.getvalue()


def _wav_to_mp3(wav_bytes: bytes) -> bytes:
    """Transcode WAV -> MP3 (64 kbps mono) via ffmpeg. Raises on failure."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", "pipe:0", "-b:a", "64k", "-ac", "1", "-f", "mp3", "pipe:1"],
        input=wav_bytes, capture_output=True, check=True,
    )
    return proc.stdout


def synthesize(text: str) -> tuple[bytes, str]:
    """
    Synthesize `text` to audio bytes.

    Returns (bytes, media_type). Prefers MP3 (small, mobile-friendly) when
    ffmpeg is present; falls back to WAV otherwise.
    """
    wav = synthesize_wav(text)
    if settings.audio_format == "mp3" and _has_ffmpeg():
        try:
            return _wav_to_mp3(wav), "audio/mpeg"
        except (subprocess.CalledProcessError, OSError) as e:
            logger.warning("MP3 transcode failed, serving WAV: %s", e)
    return wav, "audio/wav"


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def benchmark(text: str) -> dict:
    """
    Synthesize `text` and return timing — a diagnostic that can be run against
    the real VPS (`POST /admin/audio/benchmark`) to confirm on-box latency.
    """
    if not is_available():
        return {"available": False}
    t0 = time.perf_counter()
    wav = synthesize_wav(text)
    synth_s = time.perf_counter() - t0
    audio_s = _wav_duration_seconds(wav)
    return {
        "available": True,
        "voice": settings.tts_voice,
        "chars": len(text),
        "words": len(text.split()),
        "audio_seconds": round(audio_s, 2),
        "synth_seconds": round(synth_s, 3),
        "real_time_factor": round(synth_s / audio_s, 4) if audio_s else None,
        "wav_bytes": len(wav),
        "ffmpeg": _has_ffmpeg(),
    }
