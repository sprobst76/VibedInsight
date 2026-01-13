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


def _parse_topics_response(content: str) -> list[str]:
    """
    Parse LLM response to extract topics.

    Handles various formats:
    - Comma-separated: "topic1, topic2, topic3"
    - Newline-separated: "topic1\ntopic2\ntopic3"
    - With prefix: "Here are the topics:\ntopic1, topic2"
    - Numbered lists: "1. topic1\n2. topic2"
    - Bullet lists: "- topic1\n- topic2"
    """
    import re

    text = content.strip()

    # Step 1: Find the LAST colon that looks like a preamble ending
    # Look for patterns like "topics:" or "text:" and take everything after
    last_preamble_idx = -1
    for match in re.finditer(r"(topic|text|following|result)s?:\s*", text, re.IGNORECASE):
        last_preamble_idx = match.end()

    if last_preamble_idx > 0:
        text = text[last_preamble_idx:].strip()

    # Step 2: Split by commas first (if present)
    # This handles "topic1, topic2, topic3" format
    if "," in text:
        raw_topics = [t.strip() for t in text.split(",") if t.strip()]
    else:
        # Split by newlines for "topic1\ntopic2\ntopic3" format
        raw_topics = [line.strip() for line in text.split("\n") if line.strip()]

    topics = []
    for topic in raw_topics:
        # Remove numbering (1., 2., etc.) and bullets (-, *)
        cleaned = topic.strip()
        if cleaned and cleaned[0].isdigit():
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", cleaned)
        cleaned = cleaned.lstrip("-*•").strip()
        if cleaned:
            topics.append(cleaned)

    # Clean up topics
    result = []
    # Words that indicate this is preamble, not a topic
    preamble_words = {"here", "are", "relevant", "extracted", "following", "text"}

    for topic in topics:
        # Lowercase and truncate to 100 chars (DB limit)
        topic = topic.lower().strip()
        # Remove quotes if present
        topic = topic.strip("\"'")
        # Remove newlines within topic
        topic = topic.replace("\n", " ").strip()

        # Skip if too short
        if len(topic) < 2:
            continue

        # Skip if topic looks like preamble
        if "topic" in topic or "extract" in topic:
            continue

        # Skip single-word preamble fragments
        words = topic.split()
        if len(words) == 1 and words[0] in preamble_words:
            continue

        # Skip if starts with preamble phrase
        if topic.startswith("here are") or topic.startswith("the following"):
            continue

        result.append(topic[:100])

    return result


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
    except TimeoutError:
        logger.error(f"Ollama request timed out after {OLLAMA_TIMEOUT}s")
        raise
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise


async def extract_topics(text: str, existing_topics: list[str] | None = None) -> list[str]:
    """
    Extract topics/tags from text using Ollama.
    Note: existing_topics parameter is kept for backwards compatibility but ignored.
    """
    prompt_template = load_prompt("topics")
    prompt = prompt_template.format(text=text[:4000])

    logger.info("Calling Ollama for topic extraction")

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

        # Parse response - handle various LLM output formats
        content = response["message"]["content"]
        topics = _parse_topics_response(content)

        # Clean up and deduplicate
        return list(set(topics))[:10]  # Max 10 topics
    except TimeoutError:
        logger.error(f"Ollama request timed out after {OLLAMA_TIMEOUT}s")
        raise
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise


async def generate_weekly_summary(items_content: list[dict]) -> dict:
    """
    Generate a weekly summary from a list of content items.

    Args:
        items_content: List of dicts with 'title' and 'summary' keys

    Returns:
        Dict with 'summary', 'key_insights', and 'top_topics' keys
    """
    # Build content string from items
    content_parts = []
    for item in items_content[:20]:  # Limit to 20 items
        title = item.get("title", "Untitled")
        summary = item.get("summary", "No summary")
        content_parts.append(f"### {title}\n{summary}\n")

    content = "\n".join(content_parts)

    prompt_template = load_prompt("weekly_summary")
    prompt = prompt_template.format(content=content[:12000])  # Limit input length

    logger.info("Generating weekly summary with Ollama")

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
        logger.info("Weekly summary response received")

        # Parse the response
        content = response["message"]["content"]
        return _parse_weekly_summary_response(content)

    except TimeoutError:
        logger.error(f"Ollama request timed out after {OLLAMA_TIMEOUT}s")
        raise
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise


def _parse_weekly_summary_response(content: str) -> dict:
    """Parse the structured response from the weekly summary prompt."""
    result = {
        "summary": "",
        "key_insights": [],
        "top_topics": [],
    }

    current_section = None
    summary_lines = []

    for line in content.split("\n"):
        line_stripped = line.strip()

        if line_stripped.startswith("SUMMARY:"):
            current_section = "summary"
            continue
        elif line_stripped.startswith("KEY INSIGHTS:"):
            current_section = "insights"
            continue
        elif line_stripped.startswith("TOP TOPICS:"):
            current_section = "topics"
            continue

        if current_section == "summary" and line_stripped:
            summary_lines.append(line_stripped)
        elif current_section == "insights" and line_stripped.startswith("-"):
            insight = line_stripped[1:].strip()
            if insight:
                result["key_insights"].append(insight)
        elif current_section == "topics" and line_stripped:
            # Parse comma-separated topics
            topics = [t.strip() for t in line_stripped.split(",") if t.strip()]
            result["top_topics"].extend(topics)

    result["summary"] = "\n\n".join(summary_lines)
    result["top_topics"] = result["top_topics"][:10]  # Limit to 10
    result["key_insights"] = result["key_insights"][:5]  # Limit to 5

    return result
