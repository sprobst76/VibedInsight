# VibedInsight - Roadmap & TODO

This document tracks planned features, improvements, and known issues.

## v0.2.0 - Enhanced Content Management

### High Priority

- [x] **Search functionality** - Full-text search across titles and summaries ✅
- [x] **Filtering by topic** - Filter inbox by assigned topics ✅
- [x] **Notes creation** - Create notes directly in app ✅
- [x] **Sorting options** - Sort by date, title, status ✅
- [x] **Bulk actions** - Select multiple items for delete/mark read ✅

### Medium Priority

- [x] **Edit items** - Allow editing title and summary ✅
- [x] **Favorites/Bookmarks** - Mark important items ✅
- [x] **Reading progress** - Track read/unread status ✅
- [x] **Archive functionality** - Move items to archive instead of delete ✅

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

- [x] ~~User authentication~~ → Entschieden: Single-User + API-Key (2026-07) ✅
- [ ] **API rate limiting** - Protect against abuse
- [ ] **Comprehensive logging** - Structured logging with levels
- [ ] **Monitoring & metrics** - Prometheus/Grafana integration
- [ ] **Backup & restore** - Automated database backups
- [ ] **iOS support** - iOS app build and distribution

---

## Technical Debt & Improvements

### Backend

- [x] Add comprehensive API tests ✅ (laufen in CI gegen pgvector-Postgres)
- [x] Add database migrations with Alembic ✅ (Entrypoint: `alembic upgrade head`)
- [x] Implement retry logic for Ollama calls ✅
- [x] Add content deduplication ✅ (url_hash)
- [ ] Implement proper error codes
- [ ] Add API versioning

### Mobile App

- [ ] Add unit tests for providers (Notifier-Logik ist ungetestet — MockApiClient existiert, wird aber nicht genutzt)
- [ ] Integration tests entschlacken (aktuell Scheinabdeckung: `if (finder.isNotEmpty)`-Guards)
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

- [x] Long URLs may truncate in item cards ✅ v0.4.5 (Quelle einzeilig + Ellipsis, Widget-Test)
- [ ] Share sheet may not work with all apps
- [x] Settings: nach Ändern von Server-URL/API-Key nutzt die Inbox den alten
      `ApiClient` bis zum App-Neustart ✅ v0.4.5 — `ItemsNotifier` lädt beim
      Erzeugen selbst und wird bei Settings-Änderung neu erzeugt; live verifiziert
      (frische Installation → Key eintragen → Inbox lädt ohne Neustart)
- [x] Processing status doesn't auto-refresh ✅ (Polling alle 5s solange pending)

## Contributing

Want to help? Pick an item from this list and submit a PR! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

---

## Nächste Ausbaustufen (Konzept-Ideen, 2026-07)

Priorisiert nach Wert/Aufwand — Grundlage: pgvector + Embeddings sind jetzt im Ingest verdrahtet.

1. **"Frag dein Archiv" (RAG-Chat)** — ✅ v0.5.0 (P2): `POST /chat` +
   Chat-Screen mit Quellen-Chips, end-to-end gegen prod verifiziert.
   - [x] **Streaming** (v0.5.1): `/chat/stream` + streamende Chat-UI — Quellen
     erscheinen ~1–8s (sofort antippbar), Antwort läuft Token für Token ein.
   - [ ] **Prod-TTFT bleibt hardware-limitiert**: auf dem CPU-VPS dominiert die
     Prompt-Evaluation (~80s bis zum ersten Token bei qwen2.5:3b). Echte Hebel:
     kleineres/quantisiertes Modell, kürzeres `rag_context_char_budget`, oder GPU.
   - [ ] Chat-Verlauf optional persistieren; Chip-Strings (Quellen) i18n-Restarbeit.
2. **Serendipity-Resurfacing** — täglich/wöchentlich ein altes ungelesenes
   Item hochspülen ("Vor 3 Monaten gespeichert — noch relevant?").
3. **KI-Triage** — neue Items gegen bisherige Hoch-Ratings einschätzen und
   die Inbox vorsortieren (Sterne-Ratings als Trainingssignal).
4. **Capture-Kanäle** — Telegram-Bot oder Bookmarklet gegen die Ingest-API.
5. **Push für Weekly-Digest** — Notification-Tap-Handler implementieren
   (Payload wird bereits gesetzt, Handler ist leer).
6. **Audio-Digest** (P13) — persönliches NotebookLM-Pendant: Weekly-Digest als
   gesprochenes Audio (Piper TTS, lokal, ~30× Echtzeit auf CPU gemessen).
   - [x] **MVP v0.6.0**: `GET /audio/weekly/{id}` (Digest→MP3, gecacht),
     `/audio/status`, `POST /admin/audio/benchmark`; TTS-Service + Tests.
   - [x] Docker-Image auf VPS deployt (v0.6.0) + Benchmark: **~9× Echtzeit**
     (RTF 0,11) on-VPS; `/audio/weekly/3` → 200 audio/mpeg 341 KB, Cache-Hit ok.
   - [x] App: Play-Button + Player im weekly_screen (just_audio, v0.6.0+24);
     analyze sauber, 105 Tests grün, APK baut. UAT: On-Device-Audibilität nach
     Play-Release.
   - [x] „Mehr dazu" → RAG-Chat mit aus dem Digest abgeleiteter Frage (v0.6.2,
     `/chat?q=…` auto-send). Audio als Einstieg ins eigene Archiv, kein Dead-End.
   - [ ] Optional: qwen2.5 schreibt ein gesprochenes Podcast-Skript statt den
     Digest vorzulesen.

Last updated: 2026-07-11
