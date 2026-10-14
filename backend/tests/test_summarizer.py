"""Unit tests for pure summarizer helpers (no Ollama needed)."""

from app.services.summarizer import normalize_topic


def test_normalize_topic_basic():
    assert normalize_topic("  Machine Learning ") == "machine learning"


def test_normalize_topic_strips_markup():
    assert normalize_topic('- "KI-Regulierung"') == "ki-regulierung"


def test_normalize_topic_rejects_sentences():
    assert normalize_topic("this is a whole sentence about things") is None


def test_normalize_topic_rejects_too_short():
    assert normalize_topic("a") is None


def test_normalize_topic_collapses_whitespace():
    assert normalize_topic("smart \n home") == "smart home"


async def test_all_chat_paths_pass_num_ctx(monkeypatch):
    """Every chat call (summary, topics, weekly, script, stream) carries num_ctx."""
    import json

    from app.config import settings
    from app.services import summarizer

    monkeypatch.setattr(settings, "ollama_num_ctx", 4096)
    seen: list[dict] = []

    class FakeClient:
        async def chat(self, **kwargs):
            seen.append(kwargs["options"])
            if kwargs.get("stream"):

                async def gen():
                    yield {"message": {"content": "hi"}}

                return gen()
            fmt = kwargs.get("format")
            if fmt is summarizer.TOPICS_SCHEMA:
                content = json.dumps({"topics": ["ki"]})
            elif fmt is summarizer.WEEKLY_SCHEMA:
                content = json.dumps(
                    {
                        "tldr": "t",
                        "summary": "s",
                        "key_insights": [],
                        "top_topics": [],
                        "topic_clusters": [],
                        "connections": [],
                    }
                )
            else:
                content = "- x"
            return {"message": {"content": content}}

    monkeypatch.setattr(summarizer, "_ollama_client", lambda: FakeClient())

    await summarizer.generate_summary("text")
    await summarizer.extract_topics("text")
    await summarizer.generate_podcast_script("digest")
    await summarizer.generate_weekly_summary([{"title": "a", "summary": "b"}])
    _ = [c async for c in summarizer.ollama_chat_stream([{"role": "user", "content": "q"}])]

    assert len(seen) == 5
    assert all(o["num_ctx"] == 4096 for o in seen)
    # per-call options are preserved next to num_ctx
    assert any("num_predict" in o for o in seen)
