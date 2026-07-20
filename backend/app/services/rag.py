"""
RAG chat service — "Frag dein Archiv".

Flow: embed the question -> pgvector cosine search over stored item embeddings
-> build a numbered context from the top-K items -> ask Ollama to answer in
German, grounded only in that context, citing sources as [n].

The source list is derived deterministically from retrieval (not parsed from
the model's output), so the app can always map a [n] marker to a real item.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.content import ContentEmbedding, ContentItem
from app.services.embeddings import generate_embedding
from app.services.summarizer import _ollama_chat_with_retry, load_prompt

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = "Dazu finde ich nichts in deinem Archiv."


@dataclass
class RagSource:
    """One retrieved item, numbered for citation."""

    n: int
    id: str
    title: str
    url: str | None
    source: str | None
    similarity: float


@dataclass
class RagResult:
    answer: str
    sources: list[RagSource]
    used_context: bool


async def _retrieve(
    question_embedding: list[float],
    db: AsyncSession,
    top_k: int,
    min_similarity: float,
) -> list[tuple[ContentItem, float]]:
    """Top-K items by cosine similarity to the question, above the floor."""
    max_distance = 1.0 - min_similarity
    distance = ContentEmbedding.embedding.cosine_distance(question_embedding)
    result = await db.execute(
        select(ContentItem, distance.label("distance"))
        .join(ContentEmbedding, ContentEmbedding.content_id == ContentItem.id)
        .where(distance <= max_distance)
        .order_by(distance)
        .limit(top_k)
    )
    return [(item, 1.0 - float(dist)) for item, dist in result.all()]


def _build_context(
    retrieved: list[tuple[ContentItem, float]],
    char_budget: int,
) -> tuple[str, list[RagSource]]:
    """Number the retrieved items and pack them into the context budget."""
    blocks: list[str] = []
    sources: list[RagSource] = []
    used = 0

    for i, (item, similarity) in enumerate(retrieved, start=1):
        title = item.title or item.url or "Ohne Titel"
        body = (item.summary or item.raw_text or "").strip()
        header = f"[{i}] {title}"
        if item.source:
            header += f" — {item.source}"

        remaining = char_budget - used
        if remaining <= len(header) + 20 and blocks:
            break  # no room for another meaningful block
        body = body[: max(0, remaining - len(header) - 2)]

        block = f"{header}\n{body}".strip()
        blocks.append(block)
        used += len(block) + 2  # + separator

        sources.append(
            RagSource(
                n=i,
                id=str(item.id),
                title=title,
                url=item.url,
                source=item.source,
                similarity=round(similarity, 4),
            )
        )

    return "\n\n".join(blocks), sources


async def answer_question(
    question: str,
    db: AsyncSession,
    top_k: int | None = None,
) -> RagResult:
    """Answer a question from the user's archive via retrieval-augmented generation."""
    question = question.strip()
    top_k = top_k or settings.rag_top_k

    question_embedding = await generate_embedding(question)
    if question_embedding is None:
        logger.warning("RAG: embedding the question failed; cannot retrieve")
        return RagResult(
            answer=(
                "Die Frage konnte gerade nicht verarbeitet werden. "
                "Bitte später erneut versuchen."
            ),
            sources=[],
            used_context=False,
        )

    retrieved = await _retrieve(
        question_embedding, db, top_k, settings.rag_min_similarity
    )
    if not retrieved:
        return RagResult(answer=NO_CONTEXT_ANSWER, sources=[], used_context=False)

    context, sources = _build_context(retrieved, settings.rag_context_char_budget)

    prompt = (
        load_prompt("rag_answer")
        .replace("{context}", context)
        .replace("{question}", question)
    )
    answer = await _ollama_chat_with_retry([{"role": "user", "content": prompt}])

    return RagResult(answer=answer.strip(), sources=sources, used_context=True)
