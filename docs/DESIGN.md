# VibedInsight - Design Document

This document captures the vision, architecture decisions, and future direction of VibedInsight.

## Vision

VibedInsight is a **personal knowledge platform** - a self-hosted alternative to Raindrop.io + Readwise with local AI processing.

### Core Problem

Existing tools like Raindrop have limitations:
- Subscription cost vs. value
- No semantic summarization
- Newsletters treated as links, not knowledge
- No topic-based views ("What do I know about X?")
- No long-term knowledge consolidation

### Our Solution

A personal knowledge system that:
- Collects links, newsletters, PDFs, and notes
- **Automatically understands** content via AI
- **Clusters by topic** automatically
- Delivers **summaries on demand or on schedule**
- Runs **fully self-hosted** with your data under your control

## Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│                     1. CLIENTS                              │
├─────────────────────────────────────────────────────────────┤
│  Flutter App (Android/iOS)     │  Web UI (future)          │
│  - Share Sheet capture         │  - Admin dashboard        │
│  - Inbox browsing              │  - Power features         │
│  - Offline reading             │  - Bulk operations        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     2. BACKEND                              │
├─────────────────────────────────────────────────────────────┤
│  FastAPI                                                    │
│  - REST API (/items, /ingest, /topics)                     │
│  - Background processing                                    │
│  - AI integration (Ollama)                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     3. DATA LAYER                           │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL        │  Ollama          │  (Future: Qdrant)  │
│  - Content items   │  - Summaries     │  - Vector search   │
│  - Topics          │  - Topic extract │  - Semantic search │
│  - Metadata        │  - llama3.2      │                    │
└─────────────────────────────────────────────────────────────┘
```

### Why This Stack?

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Mobile | Flutter | Single codebase, Share Sheet support, offline capability |
| Backend | FastAPI | Lightweight, async, Python AI ecosystem |
| Database | PostgreSQL | Reliable, production-ready, async support |
| AI | Ollama | Local, private, no API costs |
| State | Riverpod | Type-safe, testable, Flutter-native |

## Data Model

```yaml
ContentItem:
  id: int
  content_type: link | note | article
  status: pending | processing | completed | failed
  url: string?
  title: string?
  source: string?
  raw_text: string?
  summary: string?
  topics: Topic[]
  created_at: datetime
  processed_at: datetime?

Topic:
  id: int
  name: string
  items: ContentItem[]
```

## Processing Pipeline

1. **Ingestion** - Content submitted via API or Share Sheet
2. **Extraction** - trafilatura extracts text from URLs
3. **Summarization** - Ollama generates concise summary
4. **Topic Extraction** - AI identifies relevant topics
5. **Storage** - Results saved with relationships

```
New Content → Extract Text → Generate Summary → Extract Topics → Store
     │              │               │                │            │
   [API]       [trafilatura]    [Ollama]         [Ollama]    [PostgreSQL]
```

## Current Implementation (v0.1.0)

### Implemented
- URL and text ingestion
- Background AI processing
- Summary generation
- Topic extraction
- Flutter app with Share Sheet
- Pull-to-refresh, status indicators

### Not Yet Implemented
- Search (full-text and semantic)
- Offline mode
- User authentication
- Newsletter email ingestion
- PDF support

## Future Architecture Options

### Option A: Enhanced MVP (Current Path)

Add features incrementally:
- Qdrant for semantic search
- Collections/folders
- Offline sync
- Multi-user auth

**Best for:** Quick iteration, minimal complexity

### Option B: Knowledge Graph (Future)

Add Neo4j for explicit relationships:
- "relates to", "contradicts", "extends"
- Graph exploration
- Pattern detection
- Strategic analysis

**Best for:** Long-term knowledge building, complex queries

### Recommendation

Start with Option A, but design data models to be Neo4j-compatible:
- Clean entity IDs
- Explicit relationship tracking
- Structured metadata

This is the **minimum regret strategy**.

## Input Channels (Planned)

| Source | Method | Status |
|--------|--------|--------|
| Web Links | Share Sheet, API | Implemented |
| Notes | API | Implemented |
| Newsletters | Email inbox | Planned |
| PDFs | Upload | Planned |
| Browser | Extension | Planned |

## Output Features (Planned)

| Feature | Description | Status |
|---------|-------------|--------|
| Topic summaries | "What do I know about X?" | Planned |
| Periodic digests | Weekly/monthly summaries | Planned |
| Chat interface | Ask questions about content | Planned |
| Export | Markdown, PDF, JSON | Planned |

## Design Principles

1. **Privacy first** - Self-hosted, no external dependencies required
2. **Offline capable** - Core features work without internet
3. **AI-native** - Intelligence built in, not bolted on
4. **Incrementally complex** - Start simple, add features as needed
5. **Your data** - Full control, no vendor lock-in

## Comparison to Alternatives

| Feature | Raindrop | Readwise | VibedInsight |
|---------|----------|----------|--------------|
| Self-hosted | No | No | Yes |
| AI summaries | Limited | Yes | Yes (local) |
| Semantic search | No | No | Planned |
| Knowledge graph | No | No | Planned |
| Cost | $28/year | $96/year | Free |
| Privacy | Cloud | Cloud | Local |

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Flutter Documentation](https://flutter.dev/docs)
- [Ollama](https://ollama.ai/)
- [trafilatura](https://trafilatura.readthedocs.io/)
- [Riverpod](https://riverpod.dev/)
