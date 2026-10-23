FROM python:3.12-slim

WORKDIR /app

# curl for healthcheck; ffmpeg to transcode TTS output to MP3 (Audio-Digest)
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies (single source of truth: pyproject.toml)
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "asyncpg>=0.30.0" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "httpx>=0.28.0" \
    "trafilatura>=2.0.0" \
    "ollama>=0.4.0" \
    "python-multipart>=0.0.18" \
    "alembic>=1.14.0" \
    "pgvector>=0.3.0" \
    "piper-tts>=1.5.0"

# Bake the German Piper voice into the image (~61 MB; not in git).
# TTS_VOICE / TTS_VOICES_DIR can override at runtime.
ENV TTS_VOICE=de_DE-thorsten-medium
ENV TTS_VOICES_DIR=/app/voices
RUN python -m piper.download_voices ${TTS_VOICE} --data-dir ${TTS_VOICES_DIR}

# Copy application code
COPY . .

# Source may arrive with restrictive host permissions; the unprivileged user needs read access
RUN chmod -R a+rX /app && chmod +x /app/entrypoint.sh

# Run unprivileged. /app/data holds the audio cache; piper voices stay root-owned (read-only).
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data/audio && chown -R app:app /app/data
USER app

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
