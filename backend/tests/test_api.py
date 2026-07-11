"""
API integration tests for VibedInsight backend.

These tests run against the real FastAPI app (ASGITransport).
External services (Ollama, URL fetching) are NOT called in these tests.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.fixture
async def client(apply_migrations):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def no_processing(monkeypatch):
    """Prevent ingest from spawning Ollama background tasks."""
    monkeypatch.setattr("app.routers.ingest.schedule_processing", lambda item_id: None)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# API key middleware
# ---------------------------------------------------------------------------


async def test_api_key_required_when_configured(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret-key")

    # Without key -> 401
    response = await client.get("/items")
    assert response.status_code == 401

    # Wrong key -> 401
    response = await client.get("/items", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401

    # Correct key -> 200
    response = await client.get("/items", headers={"X-API-Key": "test-secret-key"})
    assert response.status_code == 200

    # /health stays public
    response = await client.get("/health")
    assert response.status_code == 200


async def test_api_disabled_key_allows_requests(client: AsyncClient):
    # settings.api_key is empty in the test environment
    response = await client.get("/items")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Item lifecycle (ingest text -> read -> flags -> edit -> delete)
# ---------------------------------------------------------------------------


async def test_item_lifecycle(client: AsyncClient, no_processing):
    # Create a note (background processing is disabled by the fixture)
    response = await client.post(
        "/ingest/text",
        json={"title": "Lifecycle Note", "text": "Some note content", "content_type": "note"},
    )
    assert response.status_code == 200
    item = response.json()
    item_id = item["id"]
    assert item["title"] == "Lifecycle Note"
    assert item["status"] == "pending"
    assert item["rating"] == 0

    # Appears in list
    response = await client.get("/items", params={"search": "Lifecycle Note"})
    assert response.status_code == 200
    assert any(i["id"] == item_id for i in response.json()["items"])

    # Toggle favorite
    response = await client.post(f"/items/{item_id}/favorite")
    assert response.status_code == 200
    assert response.json()["is_favorite"] is True

    # Set rating (clamped to 5)
    response = await client.post(f"/items/{item_id}/rating", json={"rating": 9})
    assert response.status_code == 200
    assert response.json()["rating"] == 5

    # Edit title via PATCH
    response = await client.patch(f"/items/{item_id}", json={"title": "Edited Title"})
    assert response.status_code == 200
    assert response.json()["title"] == "Edited Title"

    # Relations endpoint returns the item with empty related_items
    response = await client.get(f"/items/{item_id}/relations")
    assert response.status_code == 200
    assert response.json()["related_items"] == []

    # Delete
    response = await client.delete(f"/items/{item_id}")
    assert response.status_code == 200

    response = await client.get(f"/items/{item_id}")
    assert response.status_code == 404


async def test_bulk_read_route_not_shadowed(client: AsyncClient, no_processing):
    """Bulk routes must not be captured by /items/{item_id}/... (regression)."""
    response = await client.post("/items/bulk/read", json={"ids": []})
    assert response.status_code == 200

    response = await client.post("/items/bulk/archive", json={"ids": []})
    assert response.status_code == 200

    response = await client.post("/items/bulk/delete", json={"ids": []})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------


async def test_weekly_current_creates_summary(client: AsyncClient):
    response = await client.get("/weekly/current")
    assert response.status_code == 200
    data = response.json()
    assert "week_start" in data
    assert "items_count" in data


async def test_weekly_list(client: AsyncClient):
    response = await client.get("/weekly")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Items — list & filter
# ---------------------------------------------------------------------------


async def test_list_items_empty(client: AsyncClient):
    response = await client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data


async def test_list_items_favorites_filter(client: AsyncClient):
    response = await client.get("/items", params={"favorites_only": "true"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


async def test_list_items_unread_filter(client: AsyncClient):
    response = await client.get("/items", params={"unread_only": "true"})
    assert response.status_code == 200


async def test_list_items_archived_filter(client: AsyncClient):
    response = await client.get("/items", params={"archived_only": "true"})
    assert response.status_code == 200


async def test_list_items_sort_by_title(client: AsyncClient):
    response = await client.get("/items", params={"sort_by": "title", "sort_order": "asc"})
    assert response.status_code == 200


async def test_list_items_sort_by_status(client: AsyncClient):
    response = await client.get("/items", params={"sort_by": "status", "sort_order": "desc"})
    assert response.status_code == 200


async def test_list_items_invalid_sort_field(client: AsyncClient):
    # Pattern validation: only date|title|status allowed
    response = await client.get("/items", params={"sort_by": "invalid_field"})
    assert response.status_code == 422


async def test_list_items_search(client: AsyncClient):
    response = await client.get("/items", params={"search": "test query"})
    assert response.status_code == 200


async def test_list_items_pagination(client: AsyncClient):
    response = await client.get("/items", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 5


async def test_list_items_page_size_limit(client: AsyncClient):
    # page_size > 100 should fail validation
    response = await client.get("/items", params={"page_size": 999})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Items — single item
# ---------------------------------------------------------------------------


async def test_get_item_not_found(client: AsyncClient):
    response = await client.get("/items/99999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Rating
# ---------------------------------------------------------------------------


async def test_set_rating_not_found(client: AsyncClient):
    response = await client.post("/items/99999999/rating", json={"rating": 3})
    assert response.status_code == 404


async def test_set_rating_invalid_payload(client: AsyncClient):
    # Missing required field
    response = await client.post("/items/99999999/rating", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


async def test_list_topics_empty(client: AsyncClient):
    response = await client.get("/topics")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_and_delete_topic(client: AsyncClient):
    # Create
    response = await client.post("/topics", json={"name": "Test-Topic-API"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test-Topic-API"
    topic_id = data["id"]

    # Verify it appears in list
    list_response = await client.get("/topics")
    assert list_response.status_code == 200
    names = [t["name"] for t in list_response.json()]
    assert "Test-Topic-API" in names

    # Delete
    delete_response = await client.delete(f"/topics/{topic_id}")
    assert delete_response.status_code == 200

    # Verify gone
    list_after = await client.get("/topics")
    names_after = [t["name"] for t in list_after.json()]
    assert "Test-Topic-API" not in names_after


async def test_delete_topic_not_found(client: AsyncClient):
    response = await client.delete("/topics/99999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ingest — validation only (no external service calls)
# ---------------------------------------------------------------------------


async def test_ingest_text_missing_fields(client: AsyncClient):
    # title and text are required
    response = await client.post("/ingest/text", json={"title": "Only title"})
    assert response.status_code == 422


async def test_ingest_text_empty_payload(client: AsyncClient):
    response = await client.post("/ingest/text", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def test_export_markdown_returns_zip(client: AsyncClient):
    response = await client.get("/export/markdown")
    assert response.status_code == 200
    assert "application/zip" in response.headers["content-type"]
    assert "content-disposition" in response.headers
    assert response.headers["content-disposition"].startswith("attachment")
    # Should be a valid (possibly empty) ZIP file
    assert len(response.content) > 0


# ---------------------------------------------------------------------------
# Graph data
# ---------------------------------------------------------------------------


async def test_graph_data(client: AsyncClient):
    response = await client.get("/items/graph/data")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert "node_count" in data
    assert "edge_count" in data
