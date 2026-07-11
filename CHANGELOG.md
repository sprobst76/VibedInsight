# Changelog

All notable changes to VibedInsight will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-07-11

### Changed — Architektur-Konsolidierung ("Single-User Rework")

#### Security & Architecture
- **API-Key-Auth**: Gesamte API (außer `/health`) verlangt jetzt `X-API-Key`
  (`API_KEY` in `.env`, Eingabe in den App-Einstellungen)
- **Vault-/JWT-Stack entfernt**: `auth.py`, `vault.py`, `services/auth.py`,
  `UserVaultEntry`, `RefreshToken` gelöscht — war nie mit dem Ingest-Flow
  verbunden (Design bleibt in PRIVACY_DESIGN_FINAL.md dokumentiert)
- SSRF-Guard im URL-Ingest (private IPs geblockt, `ALLOW_PRIVATE_URLS` opt-in)
- CORS ohne credentials; Graph-Endpoint filtert nach User

#### AI Pipeline
- Ollama **structured outputs** (JSON-Schema) für Topics und Weekly-Digest —
  ersetzt fragiles Regex-Parsing
- **Embeddings im Ingest-Flow** + **pgvector** (Image `pgvector/pgvector:pg16`);
  Relations aus Embedding-Similarity (SIMILAR) mit Shared-Topics-Fallback
- Topic-Normalisierung (deutsch, lowercase, max. 3 Wörter)
- Weekly-Digest wird sonntags 18:00 automatisch generiert (Scheduler)
- Startup-Requeue: hängende PENDING/PROCESSING-Items überleben Deploys
- `raw_text` wird nicht mehr gelöscht (Reprocessing, künftiges RAG)
- Debug-Strings erscheinen nicht mehr als Nutzer-Inhalte im Weekly

#### Deploy & Infrastruktur
- **Alembic ist Schema-Wahrheit**: Entrypoint führt `alembic upgrade head` aus
  (inkl. Legacy-DB-Erkennung); `alembic stamp` aus deploy.sh entfernt
- Migrationen 005 (Single-User-Vereinfachung) und 006 (pgvector) hinzugefügt;
  001 läuft jetzt auch auf leeren Datenbanken
- deploy.sh: Health-Check läuft im Container (war vorher immer fehlgeschlagen,
  kein Host-Port-Mapping), Backup-Validierung + Rotation
- CI: Backend-pytest mit pgvector-Service aktiviert; Flutter-Tests blockieren
  jetzt CI und Releases (continue-on-error entfernt)

#### App (Flutter)
- **Einstellungs-Screen**: Server-URL und API-Key konfigurierbar
  (hartkodierte Domain entfernt), Verbindungstest
- Drift-Cache: Migrationsstrategie + `rating`-Spalte (überlebt jetzt offline)
- Fix: Fehlermeldungen wurden durch jedes copyWith sofort gelöscht
- Fix: "All"-Filterchip-Race (Filter wurden teils nicht angewendet)
- Fix: Bulk-Read/-Archive-Routen waren durch Pfadparameter verschattet (422)
- Fix: Edit (PATCH) und Reprocess zeigen auf existierende Endpoints
- Dio-Logging nur noch im Debug-Build
- Offline-Seitenzahlen bei Topic-Filter korrigiert

### Removed
- `/content`-Router (Duplikat), 2 von 3 PRIVACY_DESIGN-Dokumenten,
  ungenutzte Schemas, duplizierte Relations-/Weekly-/Response-Builder-Logik

## [0.2.0 – 0.3.8] - 2026-01 bis 2026-02

Nicht einzeln dokumentiert (Versionsstände nur in der App gepflegt).
Wesentliche Features laut Git-History: Suche/Filter/Sortierung, Bulk-Aktionen,
Favoriten/Archiv/Read-Status, Edit, Rating (1-5 Sterne), Weekly Summary mit
Topic-Clustering + Notifications, Knowledge-Graph-Visualisierung,
Markdown-Export (Obsidian), Offline-Cache (Drift), Share-Sheet-Verbesserungen,
Auto-Refresh, Deploy-Workflow.

## [0.1.0] - 2026-01-07

### Added

#### Backend (FastAPI)
- Initial FastAPI backend with async SQLAlchemy
- PostgreSQL database with content items and topics models
- URL content extraction using trafilatura
- AI-powered summarization via Ollama (llama3.2)
- Automatic topic extraction from content
- REST API endpoints:
  - `POST /ingest/url` - Ingest content from URL
  - `POST /ingest/text` - Ingest raw text/notes
  - `GET /items` - List all content items
  - `GET /items/{id}` - Get single item with details
  - `DELETE /items/{id}` - Delete item
  - `POST /items/{id}/reprocess` - Trigger reprocessing
  - `GET /topics` - List all topics
- Health check endpoint at `/health`
- Docker Compose setup for VPS deployment
- Traefik integration with automatic HTTPS

#### Mobile App (Flutter)
- Flutter app with Material 3 design
- Light and dark theme support
- Riverpod state management
- Inbox screen with content list
- Detail screen with tabs (Summary, Original, Topics)
- Add URL dialog
- Android Share Sheet integration
- Pull-to-refresh
- Status indicators (pending, processing, completed, failed)
- Swipe actions on list items

#### DevOps
- GitHub Actions CI/CD pipeline
- Automated APK builds on tag push
- GitHub Releases with APK artifacts
- Deploy script for VPS installation

### Technical Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, asyncpg, Pydantic 2.0
- **AI**: Ollama with llama3.2 model
- **Database**: PostgreSQL 16
- **Mobile**: Flutter 3.x, Dart 3.x, Riverpod, Dio, go_router
- **Infrastructure**: Docker, Traefik, GitHub Actions

[0.4.0]: https://github.com/sprobst76/VibedInsight/releases/tag/v0.4.0
[0.1.0]: https://github.com/sprobst76/VibedInsight/releases/tag/v0.1.0
