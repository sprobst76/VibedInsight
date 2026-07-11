"""
Embeddings service for semantic similarity.

Generates vectors via Ollama; similarity search happens in PostgreSQL
(pgvector cosine distance), not in Python.
"""

import asyncio
import logging

import httpx
import ollama

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout for embedding requests
EMBEDDING_TIMEOUT = 60.0


async def generate_embedding(text: str) -> list[float] | None:
    """
    Generate an embedding vector for the given text using Ollama.

    Returns None on error (embeddings are a best-effort feature).
    """
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars]

    client = ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(EMBEDDING_TIMEOUT, connect=30.0),
    )

    try:
        response = await asyncio.wait_for(
            client.embed(model=settings.ollama_embedding_model, input=text),
            timeout=EMBEDDING_TIMEOUT,
        )

        if hasattr(response, "embeddings") and response.embeddings:
            return response.embeddings[0]
        elif isinstance(response, dict) and response.get("embeddings"):
            return response["embeddings"][0]

        logger.error(f"Unexpected embedding response format: {response}")
        return None

    except TimeoutError:
        logger.error(f"Embedding request timed out after {EMBEDDING_TIMEOUT}s")
        return None
    except Exception as e:
        logger.error(f"Embedding request failed: {e}")
        return None


async def generate_embedding_for_content(
    title: str | None, summary: str | None
) -> list[float] | None:
    """Generate embedding for a content item from title and summary."""
    combined_text = f"{title or 'Untitled'}\n\n{summary or ''}"
    return await generate_embedding(combined_text)


async def check_embedding_model_available() -> bool:
    """Check if the embedding model is available in Ollama."""
    client = ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(10.0, connect=5.0),
    )

    try:
        response = await client.list()
        available = [m.model for m in response.models]

        model_name = settings.ollama_embedding_model
        if model_name in available or f"{model_name}:latest" in available:
            return True

        logger.warning(f"Embedding model {model_name} not found. Available: {available}")
        return False

    except Exception as e:
        logger.error(f"Failed to check embedding model: {e}")
        return False
