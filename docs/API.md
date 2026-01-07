# VibedInsight API Documentation

Base URL: `https://insight.lab.YOUR_DOMAIN`

Interactive documentation available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

## Authentication

Currently, the API does not require authentication. This is planned for v1.0.0.

## Common Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid input or duplicate entry |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

## Enumerations

### ContentType

```
link    - Web content from URL
note    - User-created note
article - Long-form article
```

### ProcessingStatus

```
pending    - Queued for processing
processing - Currently being processed by AI
completed  - Successfully processed
failed     - Processing failed
```

---

## Health Check

### GET /health

Check if the API is running.

**Response**

```json
{
  "status": "healthy"
}
```

---

## Content Items

### GET /items

List all content items with pagination.

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (min: 1) |
| `page_size` | integer | 20 | Items per page (1-100) |
| `topic_id` | integer | null | Filter by topic ID |

**Response**

```json
{
  "items": [
    {
      "id": 1,
      "content_type": "link",
      "status": "completed",
      "url": "https://example.com/article",
      "title": "Example Article",
      "source": "example.com",
      "created_at": "2026-01-07T10:30:00Z",
      "topics": [
        {
          "id": 1,
          "name": "Technology",
          "created_at": "2026-01-07T10:30:00Z"
        }
      ]
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "pages": 3
}
```

---

### GET /items/{item_id}

Get a single content item with full details.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `item_id` | integer | Item ID |

**Response**

```json
{
  "id": 1,
  "content_type": "link",
  "status": "completed",
  "url": "https://example.com/article",
  "title": "Example Article",
  "source": "example.com",
  "raw_text": "Full extracted text content...",
  "summary": "AI-generated summary of the content...",
  "created_at": "2026-01-07T10:30:00Z",
  "updated_at": "2026-01-07T10:31:00Z",
  "processed_at": "2026-01-07T10:31:00Z",
  "topics": [
    {
      "id": 1,
      "name": "Technology",
      "created_at": "2026-01-07T10:30:00Z"
    }
  ]
}
```

**Error Response (404)**

```json
{
  "detail": "Item not found"
}
```

---

### DELETE /items/{item_id}

Delete a content item.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `item_id` | integer | Item ID |

**Response**

```json
{
  "status": "deleted",
  "id": 1
}
```

---

## Ingestion

### POST /ingest/url

Ingest content from a URL. The content will be extracted using trafilatura and queued for AI processing.

**Request Body**

```json
{
  "url": "https://example.com/article"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string (URL) | Yes | Valid HTTP/HTTPS URL |

**Response (200)**

Returns the created content item with `status: "pending"`.

```json
{
  "id": 2,
  "content_type": "link",
  "status": "pending",
  "url": "https://example.com/article",
  "title": "Extracted Title",
  "source": "example.com",
  "raw_text": "Extracted content...",
  "summary": null,
  "created_at": "2026-01-07T10:30:00Z",
  "updated_at": "2026-01-07T10:30:00Z",
  "processed_at": null,
  "topics": []
}
```

**Error Responses**

| Code | Detail |
|------|--------|
| 400 | "URL already ingested" |
| 400 | "Failed to extract content: {error}" |
| 400 | "Could not extract text from URL" |

---

### POST /ingest/text

Ingest raw text or a note directly.

**Request Body**

```json
{
  "title": "My Note",
  "text": "This is the content of my note...",
  "content_type": "note"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `title` | string | Yes | - | Title for the content |
| `text` | string | Yes | - | Raw text content |
| `content_type` | string | No | "note" | One of: link, note, article |

**Response (200)**

Returns the created content item with `status: "pending"`.

---

### POST /items/{item_id}/reprocess

Trigger reprocessing of an item. Useful if the initial processing failed or you want updated AI analysis.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `item_id` | integer | Item ID |

**Response (200)**

Returns the content item with `status: "pending"`.

---

## Topics

### GET /topics

List all topics, ordered alphabetically.

**Response**

```json
[
  {
    "id": 1,
    "name": "AI",
    "created_at": "2026-01-07T10:30:00Z"
  },
  {
    "id": 2,
    "name": "Technology",
    "created_at": "2026-01-07T10:35:00Z"
  }
]
```

---

### POST /topics

Create a new topic manually.

**Request Body**

```json
{
  "name": "New Topic"
}
```

**Response (200)**

```json
{
  "id": 3,
  "name": "New Topic",
  "created_at": "2026-01-07T11:00:00Z"
}
```

**Error Response (400)**

```json
{
  "detail": "Topic already exists"
}
```

---

### DELETE /topics/{topic_id}

Delete a topic.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic_id` | integer | Topic ID |

**Response**

```json
{
  "status": "deleted",
  "id": 3
}
```

---

## Processing Flow

1. Client calls `POST /ingest/url` or `POST /ingest/text`
2. Content is saved with `status: "pending"`
3. Background task picks up the item
4. Status changes to `processing`
5. AI generates summary via Ollama
6. AI extracts topics (creating new ones if needed)
7. Status changes to `completed` (or `failed` on error)
8. Client polls `GET /items/{id}` or refreshes list to see results

## Rate Limits

Currently no rate limits are enforced. This may change in future versions.

## Errors

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Validation errors (422) include field-specific details:

```json
{
  "detail": [
    {
      "loc": ["body", "url"],
      "msg": "Invalid URL format",
      "type": "value_error"
    }
  ]
}
```
