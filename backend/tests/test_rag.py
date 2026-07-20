"""
Tests for the RAG chat feature ("Frag dein Archiv").

External services (Ollama chat + embeddings) are monkeypatched — these tests
exercise retrieval, context building, the no-context path and the /chat route,
not the LLM itself.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import async_session_maker
from app.main import app
from app.models.content import ContentEmbedding, ContentItem, ProcessingStatus
from app.services import rag

EMBED_DIM = 1024


def _vec(seed: float = 1.0) -> list[float]:
    """A deterministic 1024-dim vector."""
    v = [0.0] * EMBED_DIM
    v[0] = seed
    return v


@pytest.fixture
async def client(apply_migrations):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Unit: context building
# ---------------------------------------------------------------------------


def test_build_context_numbers_sources_and_reports_similarity():
    items = [
        (
            ContentItem(
                id=uuid.uuid4(),
                title="Async in Python",
                summary="Wie async/await funktioniert.",
                source="example.com",
                url="https://example.com/async",
            ),
            0.91,
        ),
        (
            ContentItem(
                id=uuid.uuid4(),
                title="Event Loops",
                summary="Der Event-Loop koordiniert Coroutinen.",
                source="docs.example",
                url=None,
            ),
            0.80,
        ),
    ]

    context, sources = rag._build_context(items, char_budget=6000)

    assert "[1] Async in Python — example.com" in context
    assert "[2] Event Loops — docs.example" in context
    assert [s.n for s in sources] == [1, 2]
    assert sources[0].title == "Async in Python"
    assert sources[0].similarity == pytest.approx(0.91)
    assert sources[1].url is None


def test_build_context_respects_char_budget():
    items = [
        (
            ContentItem(
                id=uuid.uuid4(),
                title=f"Item {i}",
                summary="x" * 500,
                source=None,
                url=None,
            ),
            0.5,
        )
        for i in range(10)
    ]

    context, sources = rag._build_context(items, char_budget=800)

    assert len(context) <= 900  # budget + a little slack for the final block
    assert len(sources) < 10  # not everything fit


# ---------------------------------------------------------------------------
# Unit: no-context path must not call the LLM
# ---------------------------------------------------------------------------


async def test_answer_question_without_hits_skips_llm(monkeypatch):
    monkeypatch.setattr(rag, "generate_embedding", lambda text: _fake_async(_vec()))

    async def _no_hits(*args, **kwargs):
        return []

    monkeypatch.setattr(rag, "_retrieve", _no_hits)

    def _boom(*args, **kwargs):
        raise AssertionError("LLM must not be called when there is no context")

    monkeypatch.setattr(rag, "_ollama_chat_with_retry", _boom)

    async with async_session_maker() as db:
        result = await rag.answer_question("Was weiß ich über X?", db)

    assert result.used_context is False
    assert result.sources == []
    assert result.answer == rag.NO_CONTEXT_ANSWER


# ---------------------------------------------------------------------------
# Integration: /chat over a seeded item + embedding
# ---------------------------------------------------------------------------


async def test_chat_endpoint_answers_from_seeded_item(client, monkeypatch):
    # Seed one item with an embedding.
    async with async_session_maker() as db:
        item = ContentItem(
            title="Async in Python",
            summary="async/await ermöglicht nebenläufigen Code.",
            source="example.com",
            url="https://example.com/async",
            status=ProcessingStatus.COMPLETED,
        )
        db.add(item)
        await db.flush()
        db.add(
            ContentEmbedding(
                content_id=item.id, embedding=_vec(), model="mxbai-embed-large"
            )
        )
        await db.commit()

    # Same vector => cosine distance 0 => similarity 1.0 (>= floor).
    monkeypatch.setattr(rag, "generate_embedding", lambda text: _fake_async(_vec()))

    async def _fake_chat(messages, **kwargs):
        return "async/await ermöglicht nebenläufigen Code [1]."

    monkeypatch.setattr(rag, "_ollama_chat_with_retry", _fake_chat)

    response = await client.post("/chat", json={"question": "Wie funktioniert async?"})

    assert response.status_code == 200
    data = response.json()
    assert data["used_context"] is True
    assert "[1]" in data["answer"]
    assert len(data["sources"]) >= 1
    top = data["sources"][0]
    assert top["n"] == 1
    assert top["title"] == "Async in Python"
    assert top["similarity"] >= 0.99


async def test_chat_endpoint_rejects_empty_question(client):
    response = await client.post("/chat", json={"question": "   "})
    assert response.status_code == 422


def _fake_async(value):
    """Wrap a value in an awaitable (for monkeypatching async functions)."""

    async def _coro():
        return value

    return _coro()
