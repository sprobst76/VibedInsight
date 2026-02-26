"""
API integration tests for VibedInsight backend.

These tests run against the real FastAPI app (ASGITransport).
Authentication uses get_dev_or_current_user which falls back to dev user.
External services (Ollama, URL fetching) are NOT called in these tests.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


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
