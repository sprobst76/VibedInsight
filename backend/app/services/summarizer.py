"""
LLM services: summaries, topic extraction, weekly digest.

Topics and the weekly digest use Ollama structured outputs (a JSON schema is
passed as `format`), so the model is constrained to valid JSON — no more
regex parsing of free-form LLM text.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx
import ollama

from app.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Timeout for Ollama requests (5 minutes for long texts)
OLLAMA_TIMEOUT = 300.0

# Retry config
MAX_RETRIES = 2
RETRY_BACKOFF = [2.0, 5.0]  # seconds between attempts


TOPICS_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        }
    },
    "required": ["topics"],
}

WEEKLY_SCHEMA = {
    "type": "object",
    "properties": {
        "tldr": {"type": "string"},
        "summary": {"type": "string"},
        "key_insights": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "top_topics": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        "topic_clusters": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "article_count": {"type": "integer"},
                    "description": {"type": "string"},
                },
                "required": ["name", "article_count", "description"],
            },
        },
        "connections": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
    },
    "required": ["tldr", "summary", "key_insights", "top_topics", "topic_clusters", "connections"],
}


def _ollama_client() -> ollama.AsyncClient:
    return ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(OLLAMA_TIMEOUT, connect=30.0),
    )


# Only try to auto-pull a missing chat model once per process
_pull_attempted = False


async def _pull_missing_model() -> bool:
    """Pull the configured chat model if Ollama reports it missing."""
    global _pull_attempted
    if _pull_attempted:
        return False
    _pull_attempted = True

    logger.warning(f"Chat model {settings.ollama_model} missing — pulling from Ollama registry")
    client = ollama.AsyncClient(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(1800.0, connect=30.0),
    )
    try:
        await client.pull(settings.ollama_model)
        logger.info(f"Model {settings.ollama_model} pulled successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to pull model {settings.ollama_model}: {e}")
        return False


async def _ollama_chat_with_retry(
    messages: list[dict],
    format: dict | None = None,
    timeout: float = OLLAMA_TIMEOUT,
    options: dict | None = None,
) -> str:
    """Call Ollama chat with automatic retry on failure; returns message content."""
    client = _ollama_client()
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(
                client.chat(
                    model=settings.ollama_model,
                    messages=messages,
                    format=format,
                    options=options,
                ),
                timeout=timeout,
            )
            return response["message"]["content"]
        except Exception as e:
            last_error = e
            if "not found" in str(e).lower() and await _pull_missing_model():
                continue  # model is available now, retry immediately
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                logger.warning(f"Ollama attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Ollama failed after {MAX_RETRIES + 1} attempts: {e}")
    raise last_error  # type: ignore[misc]


async def ollama_chat_stream(
    messages: list[dict],
    options: dict | None = None,
):
    """Stream an Ollama chat response, yielding message-content chunks.

    No retry: retrying mid-stream would duplicate already-yielded text, so a
    failure propagates to the caller (which surfaces it as an error event).
    """
    client = _ollama_client()
    stream = await client.chat(
        model=settings.ollama_model,
        messages=messages,
        stream=True,
        options=options,
    )
    async for part in stream:
        try:
            content = part["message"]["content"]
        except (KeyError, TypeError):
            content = ""
        if content:
            yield content


def load_prompt(name: str) -> str:
    """Load a prompt template from file."""
    prompt_file = PROMPTS_DIR / f"{name}.txt"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt template '{name}' not found")


async def generate_summary(text: str) -> str:
    """Generate a summary of the given text using Ollama."""
    prompt = load_prompt("summary").format(text=text[:8000])
    logger.info(f"Calling Ollama at {settings.ollama_base_url} with model {settings.ollama_model}")
    return await _ollama_chat_with_retry([{"role": "user", "content": prompt}])


def normalize_topic(raw: str) -> str | None:
    """Normalize a topic name: lowercase, trimmed, no markup, sane length."""
    topic = raw.strip().lower().replace("\n", " ").replace("_", " ")
    topic = re.sub(r"\s+", " ", topic)
    topic = topic.strip("-*• .\"'")
    if len(topic) < 2 or len(topic) > 100:
        return None
    # More than 4 words is a sentence, not a topic
    if len(topic.split()) > 4:
        return None
    return topic


async def extract_topics(text: str) -> list[str]:
    """Extract normalized topics from text via structured output."""
    prompt = load_prompt("topics").format(text=text[:4000])
    content = await _ollama_chat_with_retry(
        [{"role": "user", "content": prompt}],
        format=TOPICS_SCHEMA,
    )

    try:
        raw_topics = json.loads(content).get("topics", [])
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"Topic extraction returned invalid JSON: {e}; content: {content[:200]}")
        return []

    topics: list[str] = []
    for raw in raw_topics:
        if not isinstance(raw, str):
            continue
        topic = normalize_topic(raw)
        if topic and topic not in topics:
            topics.append(topic)

    return topics[:5]


def _build_topics_summary(topics_by_item: dict[str, list[str]]) -> str:
    """Build a topics overview string from topics data."""
    if not topics_by_item:
        return "Keine Themen zugewiesen."

    topic_counts: dict[str, int] = {}
    for topics in topics_by_item.values():
        for topic in topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    lines = [f"- {topic}: {count} Artikel" for topic, count in sorted_topics[:15]]
    return "\n".join(lines) if lines else "Keine Themen zugewiesen."


def _build_relations_summary(relations: list[dict]) -> str:
    """Build a relations overview string."""
    if not relations:
        return "Keine Verbindungen zwischen Artikeln erkannt."

    lines = []
    seen_pairs = set()

    for rel in relations[:20]:
        source = rel.get("source_title", "Unbekannt")
        target = rel.get("target_title", "Unbekannt")
        rel_type = rel.get("relation_type", "related")

        pair_key = tuple(sorted([source, target]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        type_display = {
            "related": "verwandt mit",
            "extends": "erweitert",
            "contradicts": "widerspricht",
            "similar": "ähnlich zu",
            "references": "referenziert",
        }.get(rel_type, "verbunden mit")

        lines.append(f'- "{source}" {type_display} "{target}"')

    return "\n".join(lines) if lines else "Keine Verbindungen zwischen Artikeln erkannt."


async def generate_weekly_summary(
    items_content: list[dict],
    topics_by_item: dict[str, list[str]] | None = None,
    relations: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Generate a weekly summary from a list of content items.

    Returns a dict with tldr, summary, key_insights, top_topics,
    topic_clusters and connections (all guaranteed present).
    """
    content_parts = []
    for item in items_content[:20]:
        title = item.get("title", "Untitled")
        summary = item.get("summary", "No summary")
        content_parts.append(f"### {title}\n{summary}\n")
    content = "\n".join(content_parts)

    prompt = load_prompt("weekly_summary").format(
        content=content[:10000],
        topics_summary=_build_topics_summary(topics_by_item or {}),
        relations_summary=_build_relations_summary(relations or []),
    )

    logger.info("Generating weekly summary with Ollama (structured output)")
    raw = await _ollama_chat_with_retry(
        [{"role": "user", "content": prompt}],
        format=WEEKLY_SCHEMA,
    )

    parsed = json.loads(raw)

    def str_list(values: Any, limit: int) -> list[str]:
        if not isinstance(values, list):
            return []
        return [v.strip() for v in values if isinstance(v, str) and v.strip()][:limit]

    clusters = []
    for cluster in parsed.get("topic_clusters", []) or []:
        if not isinstance(cluster, dict) or not cluster.get("name"):
            continue
        clusters.append(
            {
                "name": str(cluster.get("name", "")).strip(),
                "article_count": int(cluster.get("article_count", 0) or 0),
                "description": str(cluster.get("description", "")).strip(),
            }
        )

    return {
        "tldr": str(parsed.get("tldr", "")).strip()[:500],
        "summary": str(parsed.get("summary", "")).strip(),
        "key_insights": str_list(parsed.get("key_insights"), 5),
        "top_topics": str_list(parsed.get("top_topics"), 10),
        "topic_clusters": clusters[:8],
        "connections": str_list(parsed.get("connections"), 10),
    }
