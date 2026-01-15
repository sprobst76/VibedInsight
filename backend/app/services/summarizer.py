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


def _build_topics_summary(topics_by_item: dict[str, list[str]]) -> str:
    """Build a topics overview string from topics data."""
    if not topics_by_item:
        return "Keine Themen zugewiesen."

    # Count topic occurrences
    topic_counts: dict[str, int] = {}
    for topics in topics_by_item.values():
        for topic in topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    # Sort by count
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

    lines = []
    for topic, count in sorted_topics[:15]:  # Limit to 15 topics
        lines.append(f"- {topic}: {count} Artikel")

    return "\n".join(lines) if lines else "Keine Themen zugewiesen."


def _build_relations_summary(relations: list[dict]) -> str:
    """Build a relations overview string."""
    if not relations:
        return "Keine Verbindungen zwischen Artikeln erkannt."

    lines = []
    seen_pairs = set()

    for rel in relations[:20]:  # Limit to 20 relations
        source = rel.get("source_title", "Unbekannt")
        target = rel.get("target_title", "Unbekannt")
        rel_type = rel.get("relation_type", "related")

        # Avoid duplicates (A-B = B-A)
        pair_key = tuple(sorted([source, target]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        type_display = {
            "related": "verwandt mit",
            "extends": "erweitert",
            "contradicts": "widerspricht",
            "similar": "aehnlich zu",
            "references": "referenziert",
        }.get(rel_type, "verbunden mit")

        lines.append(f'- "{source}" {type_display} "{target}"')

    return "\n".join(lines) if lines else "Keine Verbindungen zwischen Artikeln erkannt."


async def generate_weekly_summary(
    items_content: list[dict],
    topics_by_item: dict[str, list[str]] | None = None,
    relations: list[dict] | None = None,
) -> dict:
    """
    Generate a weekly summary from a list of content items.

    Args:
        items_content: List of dicts with 'title' and 'summary' keys
        topics_by_item: Dict mapping item titles to their topics
        relations: List of relation dicts with source_title, target_title, relation_type

    Returns:
        Dict with 'tldr', 'summary', 'key_insights', 'top_topics', 'topic_clusters', 'connections'
    """
    # Build content string from items
    content_parts = []
    for item in items_content[:20]:  # Limit to 20 items
        title = item.get("title", "Untitled")
        summary = item.get("summary", "No summary")
        content_parts.append(f"### {title}\n{summary}\n")

    content = "\n".join(content_parts)

    # Build topics and relations summaries
    topics_summary = _build_topics_summary(topics_by_item or {})
    relations_summary = _build_relations_summary(relations or [])

    prompt_template = load_prompt("weekly_summary")
    prompt = prompt_template.format(
        content=content[:10000],
        topics_summary=topics_summary,
        relations_summary=relations_summary,
    )

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
        response_content = response["message"]["content"]
        return _parse_weekly_summary_response(response_content)

    except TimeoutError:
        logger.error(f"Ollama request timed out after {OLLAMA_TIMEOUT}s")
        raise
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise


def _parse_weekly_summary_response(content: str) -> dict:
    """Parse the structured response from the weekly summary prompt."""
    import re

    result = {
        "tldr": "",
        "summary": "",
        "key_insights": [],
        "top_topics": [],
        "topic_clusters": [],
        "connections": [],
    }

    current_section = None
    summary_lines = []
    tldr_lines = []
    cluster_lines = []
    connection_lines = []

    for line in content.split("\n"):
        line_stripped = line.strip()

        # Detect section headers
        if line_stripped.startswith("TL;DR:") or line_stripped == "TL;DR":
            current_section = "tldr"
            # Handle inline content after colon
            rest = line_stripped.replace("TL;DR:", "").replace("TL;DR", "").strip()
            if rest:
                tldr_lines.append(rest)
            continue
        elif line_stripped.startswith("THEMEN-CLUSTER:") or line_stripped == "THEMEN-CLUSTER":
            current_section = "clusters"
            continue
        elif line_stripped.startswith("VERBINDUNGEN:") or line_stripped == "VERBINDUNGEN":
            current_section = "connections"
            continue
        elif line_stripped.startswith("ZUSAMMENFASSUNG:") or line_stripped == "ZUSAMMENFASSUNG":
            current_section = "summary"
            continue
        elif line_stripped.startswith("KEY INSIGHTS:") or line_stripped == "KEY INSIGHTS":
            current_section = "insights"
            continue
        elif line_stripped.startswith("TOP TOPICS:") or line_stripped == "TOP TOPICS":
            current_section = "topics"
            continue
        # Fallback for old format
        elif line_stripped.startswith("SUMMARY:"):
            current_section = "summary"
            continue

        # Collect content based on current section
        if current_section == "tldr" and line_stripped:
            tldr_lines.append(line_stripped)
        elif current_section == "clusters" and line_stripped:
            cluster_lines.append(line_stripped)
        elif current_section == "connections" and line_stripped.startswith("-"):
            connection_lines.append(line_stripped[1:].strip())
        elif current_section == "summary" and line_stripped:
            summary_lines.append(line_stripped)
        elif current_section == "insights" and line_stripped.startswith("-"):
            insight = line_stripped[1:].strip()
            if insight:
                result["key_insights"].append(insight)
        elif current_section == "topics" and line_stripped:
            # Parse comma-separated topics
            topics = [t.strip() for t in line_stripped.split(",") if t.strip()]
            result["top_topics"].extend(topics)

    # Process TL;DR
    result["tldr"] = " ".join(tldr_lines)[:500] if tldr_lines else ""

    # Process summary
    result["summary"] = "\n\n".join(summary_lines)

    # Parse topic clusters - format: **Name** (X Artikel): Beschreibung
    cluster_pattern = r"\*\*(.+?)\*\*\s*\((\d+)\s*Artikel\):\s*(.+)"
    for line in cluster_lines:
        match = re.match(cluster_pattern, line)
        if match:
            result["topic_clusters"].append({
                "name": match.group(1).strip(),
                "article_count": int(match.group(2)),
                "description": match.group(3).strip(),
            })

    # Process connections
    result["connections"] = connection_lines[:10]  # Limit to 10

    # Limits
    result["top_topics"] = result["top_topics"][:10]
    result["key_insights"] = result["key_insights"][:5]
    result["topic_clusters"] = result["topic_clusters"][:8]

    return result
