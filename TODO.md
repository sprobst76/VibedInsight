# VibedInsight - Roadmap & TODO

This document tracks planned features, improvements, and known issues.

## v0.2.0 - Enhanced Content Management

### High Priority

- [x] **Search functionality** - Full-text search across titles and summaries ✅
- [x] **Filtering by topic** - Filter inbox by assigned topics ✅
- [x] **Notes creation** - Create notes directly in app ✅
- [ ] **Sorting options** - Sort by date, title, status
- [ ] **Bulk actions** - Select multiple items for delete/reprocess

### Medium Priority

- [ ] **Edit items** - Allow editing title and notes
- [ ] **Favorites/Bookmarks** - Mark important items
- [ ] **Reading progress** - Track read/unread status
- [ ] **Archive functionality** - Move items to archive instead of delete

---

## Offline Mode (geplant)

### Ziel
Items lokal cachen für Offline-Lesen und später synchronisieren.

### Technischer Ansatz
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Flutter App    │────▶│  Local SQLite   │────▶│  Remote API     │
│  (UI)           │     │  (drift)        │     │  (FastAPI)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Herausforderungen

1. **Speicherverbrauch**
   - Jeder Content-Item hat `raw_text` (kann mehrere KB sein)
   - Summaries + Topics kommen dazu
   - Bei 1000+ Items: mehrere MB lokaler Speicher

2. **Sync-Konflikte**
   - Was passiert wenn offline erstellt und online geändert?
   - Last-write-wins vs. Merge-Strategie?

3. **Initiale Sync-Zeit**
   - Alle Items beim ersten Start laden?
   - Oder nur Metadaten + Lazy-Load Content?

4. **Cache-Invalidierung**
   - Wann wird Cache aktualisiert?
   - TTL (Time-to-Live) vs. Event-basiert?

### Implementierungsoptionen

**Option A: Einfacher Cache (empfohlen für Start)**
- Nur gelesene Items cachen
- Online-First, Fallback auf Cache bei Fehler
- Kein Offline-Erstellen

**Option B: Voller Offline-Support**
- Alle Items syncen
- Offline-Queue für neue Items
- Konflikt-Resolution nötig

---

## Knowledge Graph - Lightweight Optionen

### Das Problem
Neo4j braucht viel RAM (min. 512MB-1GB) und ist für kleine VPS überdimensioniert.

### Alternativen für "Knowledge Graph für Arme"

| Option | RAM | Vorteile | Nachteile |
|--------|-----|----------|-----------|
| **PostgreSQL + Join-Tabellen** | ~50MB | Bereits vorhanden, einfach | Keine echten Graph-Queries |
| **SQLite + Recursive CTEs** | ~10MB | Sehr leicht, lokal | Begrenzte Graph-Operationen |
| **DuckDB** | ~100MB | Analytisch stark, embedded | Nicht für OLTP optimiert |
| **Kuzu** | ~50MB | Embedded Graph DB | Noch jung, weniger Tooling |
| **EdgeDB** | ~200MB | Graph + Relational | Mehr Overhead als Postgres |

### Empfehlung: "Pseudo-Graph" in PostgreSQL

Statt Neo4j:
```sql
-- Beziehungstabelle
CREATE TABLE item_relations (
    source_id INT REFERENCES content_items(id),
    target_id INT REFERENCES content_items(id),
    relation_type VARCHAR(50),  -- 'related', 'contradicts', 'extends'
    confidence FLOAT,
    created_at TIMESTAMP
);

-- Topics als implizite Verbindungen nutzen
-- Items mit gleichen Topics sind "related"
```

**Vorteile:**
- Kein zusätzlicher Service
- ~0 MB extra RAM
- Ollama kann Beziehungen beim Processing extrahieren

**Einschränkungen:**
- Keine tiefe Graph-Traversierung (nur 1-2 Hops praktikabel)
- Kein PageRank oder ähnliche Graph-Algorithmen

### Wann doch Neo4j?
- >10.000 Items mit komplexen Beziehungen
- Graph-Exploration als Kernfeature
- "Was beeinflusst X über 3+ Ecken?"

---

## v0.3.0 - Collections & Organization

- [ ] **Collections/Folders** - Group items into custom collections
- [ ] **Tags** - User-defined tags in addition to AI topics
- [ ] **Smart collections** - Auto-collections based on rules
- [ ] **Drag & drop organization** - Reorder items within collections

## v0.4.0 - Enhanced AI Features

- [ ] **Custom prompts** - User-configurable summarization prompts
- [ ] **Multiple AI models** - Support different Ollama models per task
- [ ] **Key insights extraction** - Extract bullet points from content
- [ ] **Related content** - AI-powered content recommendations (via Pseudo-Graph)
- [ ] **Question answering** - Ask questions about saved content

## v0.5.0 - Sync & Export

- [ ] **Export options** - Export to Markdown, PDF, JSON
- [ ] **Import from other services** - Raindrop.io, Pocket, Instapaper
- [ ] **RSS feed support** - Subscribe to feeds for auto-ingestion
- [ ] **Browser extension** - Quick save from desktop browser
- [ ] **Multi-device sync** - Sync state across devices

## v1.0.0 - Production Ready

- [ ] **User authentication** - Multi-user support with accounts
- [ ] **API rate limiting** - Protect against abuse
- [ ] **Comprehensive logging** - Structured logging with levels
- [ ] **Monitoring & metrics** - Prometheus/Grafana integration
- [ ] **Backup & restore** - Automated database backups
- [ ] **iOS support** - iOS app build and distribution

---

## Technical Debt & Improvements

### Backend

- [ ] Add comprehensive API tests
- [ ] Implement request validation middleware
- [ ] Add database migrations with Alembic
- [ ] Implement retry logic for Ollama calls
- [ ] Add content deduplication
- [ ] Implement proper error codes
- [ ] Add API versioning

### Mobile App

- [ ] Add unit tests for providers
- [ ] Add integration tests
- [ ] Implement proper error handling UI
- [ ] Add loading skeletons
- [ ] Optimize list performance for large datasets
- [ ] Add accessibility features
- [ ] Localization support (i18n)

### Infrastructure

- [ ] Add health check for Ollama dependency
- [ ] Implement graceful shutdown
- [ ] Add container resource limits
- [ ] Set up log rotation
- [ ] Create Kubernetes manifests (optional)

## Known Issues

- [ ] Long URLs may truncate in item cards
- [ ] Share sheet may not work with all apps
- [ ] Processing status doesn't auto-refresh

## Contributing

Want to help? Pick an item from this list and submit a PR! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

Last updated: 2026-01-07
