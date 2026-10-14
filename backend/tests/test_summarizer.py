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


def _capture_warnings(monkeypatch) -> list[str]:
    """Collect summarizer warnings (caplog is unreliable with the app's logging setup)."""
    from app.services import summarizer

    captured: list[str] = []
    monkeypatch.setattr(
        summarizer.logger, "warning", lambda msg, *a, **k: captured.append(msg % a if a else msg)
    )
    return captured


def test_fit_text_cuts_and_warns(monkeypatch):
    from app.config import settings
    from app.services.summarizer import fit_text

    monkeypatch.setattr(settings, "ollama_num_ctx", 1000)
    long_text = "x" * 10_000
    warnings = _capture_warnings(monkeypatch)
    out = fit_text(long_text, template_chars=350, answer_tokens=400, context="item 42")
    # (1000 - 400 - 100) tokens * 3.5 = 1750 chars
    assert len(out) == 1750
    assert "item 42" in " ".join(warnings)

    assert fit_text("short", template_chars=350, answer_tokens=400) == "short"


async def test_prompt_eval_count_near_limit_warns(monkeypatch):
    from app.config import settings
    from app.services import summarizer

    monkeypatch.setattr(settings, "ollama_num_ctx", 1000)

    class FakeClient:
        def __init__(self, used):
            self.used = used

        async def chat(self, **kwargs):
            return {"message": {"content": "ok"}, "prompt_eval_count": self.used}

    monkeypatch.setattr(summarizer, "_ollama_client", lambda: FakeClient(980))
    warnings = _capture_warnings(monkeypatch)
    await summarizer.generate_summary("hello", context="item 7")
    assert "truncated" in " ".join(warnings) and "item 7" in " ".join(warnings)

    warnings.clear()
    monkeypatch.setattr(summarizer, "_ollama_client", lambda: FakeClient(400))
    await summarizer.generate_summary("hello", context="item 7")
    assert not warnings


def _weekly_fake_client(calls: list[dict]):
    import json

    from app.services import summarizer

    class FakeClient:
        async def chat(self, **kwargs):
            calls.append(kwargs)
            fmt = kwargs.get("format")
            if fmt is summarizer.CLUSTER_SCHEMA:
                content = json.dumps(
                    {"theme": "T", "summary": "Zusammenfassung", "key_points": ["a"]}
                )
            else:
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
            return {"message": {"content": content}}

    return FakeClient()


def _items_and_topics(n_per_topic=2, topics=("ki", "recht", "energie")):
    items, by_item = [], {}
    for t in topics:
        for k in range(n_per_topic):
            title = f"{t}-{k}"
            items.append({"title": title, "summary": f"Text zu {t}"})
            by_item[title] = [t]
    return items, by_item


async def test_weekly_mapreduce_three_clusters(monkeypatch):
    from app.config import settings
    from app.services import summarizer

    monkeypatch.setattr(settings, "ollama_num_ctx", 4096)
    monkeypatch.setattr(settings, "weekly_mapreduce_threshold", 4)
    calls: list[dict] = []
    monkeypatch.setattr(summarizer, "_ollama_client", lambda: _weekly_fake_client(calls))

    items, by_item = _items_and_topics()
    progress: list[tuple[str, int, int]] = []
    result = await summarizer.generate_weekly_summary(
        items, by_item, [], progress=lambda *a: progress.append(a)
    )

    map_calls = [c for c in calls if c["format"] is summarizer.CLUSTER_SCHEMA]
    reduce_calls = [c for c in calls if c["format"] is summarizer.WEEKLY_SCHEMA]
    assert len(map_calls) == 3
    assert len(reduce_calls) == 1
    assert all(c["options"]["num_ctx"] == 4096 for c in calls)
    # reduce input is the cluster summaries, not the raw item texts
    reduce_prompt = reduce_calls[0]["messages"][0]["content"]
    assert "Zusammenfassung" in reduce_prompt and "(2 Artikel)" in reduce_prompt
    assert progress == [("cluster", 1, 3), ("cluster", 2, 3), ("cluster", 3, 3), ("reduce", 3, 3)]
    assert result["tldr"] == "t"


async def test_weekly_below_threshold_is_single_call(monkeypatch):
    from app.config import settings
    from app.services import summarizer

    monkeypatch.setattr(settings, "weekly_mapreduce_threshold", 10)
    calls: list[dict] = []
    monkeypatch.setattr(summarizer, "_ollama_client", lambda: _weekly_fake_client(calls))

    items, by_item = _items_and_topics()
    await summarizer.generate_weekly_summary(items, by_item, [])
    assert len(calls) == 1
    assert calls[0]["format"] is summarizer.WEEKLY_SCHEMA


def test_group_into_clusters_caps_and_collects_rest():
    from app.services.summarizer import OTHER_CLUSTER, group_into_clusters

    topics = [f"t{i}" for i in range(9)]
    items, by_item = _items_and_topics(n_per_topic=1, topics=topics)
    items.append({"title": "ohne", "summary": "x"})
    by_item["ohne"] = []

    clusters = group_into_clusters(items, by_item, max_clusters=6)
    assert len(clusters) == 6
    assert clusters[-1][0] == OTHER_CLUSTER
    assert sum(len(c[1]) for c in clusters) == len(items)
