import asyncio
import logging
from pathlib import Path

import httpx
import ollama

from app.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Timeout for Ollama requests (5 minutes for long texts)
OLLAMA_TIMEOUT = 300.0


def load_prompt(name: str) -> str:
    """Load a prompt template from file."""
    prompt_file = PROMPTS_DIR / f"{name}.txt"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt template '{name}' not found")


async def generate_summary(text: str, language: str = "auto") -> str:
    """
    Generate a summary of the given text using Ollama.
    """
    prompt_template = load_prompt("summary")
    prompt = prompt_template.format(text=text[:8000])  # Limit input length

    logger.info(f"Calling Ollama at {settings.ollama_base_url} with model {settings.ollama_model}")

    # Create client with custom timeout
    client = ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(OLLAMA_TIMEOUT, connect=30.0),
    )

    try:
        response = await asyncio.wait_for(
            client.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=OLLAMA_TIMEOUT,
        )
        logger.info("Ollama summary response received")
        return response["message"]["content"]
    except asyncio.TimeoutError:
        logger.error(f"Ollama request timed out after {OLLAMA_TIMEOUT}s")
        raise
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise


async def extract_topics(text: str, existing_topics: list[str] | None = None) -> list[str]:
    """
    Extract topics/tags from text using Ollama.
    """
    prompt_template = load_prompt("topics")
    existing = ", ".join(existing_topics) if existing_topics else "none"
    prompt = prompt_template.format(text=text[:4000], existing_topics=existing)

    logger.info(f"Calling Ollama for topic extraction")

    # Create client with custom timeout
    client = ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(OLLAMA_TIMEOUT, connect=30.0),
    )

    try:
        response = await asyncio.wait_for(
            client.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=OLLAMA_TIMEOUT,
        )
        logger.info("Ollama topics response received")

        # Parse response - expect comma-separated topics
        content = response["message"]["content"]
        topics = [t.strip().lower() for t in content.split(",") if t.strip()]

        # Clean up and deduplicate
        return list(set(topics))[:10]  # Max 10 topics
    except asyncio.TimeoutError:
        logger.error(f"Ollama request timed out after {OLLAMA_TIMEOUT}s")
        raise
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise
