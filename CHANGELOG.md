# Changelog

All notable changes to VibedInsight will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/sprobst76/VibedInsight/releases/tag/v0.1.0
