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
