"""
Embeddings service for semantic similarity.

Uses Ollama's embedding models (nomic-embed-text, mxbai-embed-large, etc.)
to generate text embeddings for content similarity calculation.
"""

import asyncio
import logging
import math

import httpx
import ollama

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout for embedding requests
EMBEDDING_TIMEOUT = 60.0


async def generate_embedding(text: str) -> list[float] | None:
    """
    Generate an embedding vector for the given text using Ollama.

    Args:
        text: The text to embed (will be truncated if too long)

    Returns:
        List of floats representing the embedding vector, or None on error
    """
    # Truncate text to avoid token limits (nomic-embed-text has 8192 token context)
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars]

    logger.info(f"Generating embedding with {settings.ollama_embedding_model}")

    client = ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(EMBEDDING_TIMEOUT, connect=30.0),
    )

    try:
        response = await asyncio.wait_for(
            client.embed(
                model=settings.ollama_embedding_model,
                input=text,
            ),
            timeout=EMBEDDING_TIMEOUT,
        )
        logger.info("Embedding generated successfully")

        # Response contains 'embeddings' list with one vector
        # Handle both dict-style and object-style responses
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


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    if len(vec1) != len(vec2):
        raise ValueError(f"Vector dimensions don't match: {len(vec1)} vs {len(vec2)}")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


async def generate_embedding_for_content(title: str, summary: str) -> list[float] | None:
    """
    Generate embedding for a content item using title and summary.

    Combines title and summary for better semantic representation.
    """
    # Combine title and summary with separator
    combined_text = f"{title or 'Untitled'}\n\n{summary or ''}"
    return await generate_embedding(combined_text)


async def check_embedding_model_available() -> bool:
    """Check if the embedding model is available in Ollama."""
    client = ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(10.0, connect=5.0),
    )

    try:
        # List available models (ollama library returns objects, not dicts)
        response = await client.list()
        # Access .models attribute and .model on each Model object
        available = [m.model for m in response.models]

        # Check if embedding model is available (with or without :latest tag)
        model_name = settings.ollama_embedding_model
        if model_name in available or f"{model_name}:latest" in available:
            logger.info(f"Embedding model {model_name} is available")
            return True

        logger.warning(f"Embedding model {model_name} not found. Available: {available}")
        logger.warning(f"Pull it with: ollama pull {model_name}")
        return False

    except Exception as e:
        logger.error(f"Failed to check embedding model: {e}")
        return False
