# VibedInsight - Roadmap & TODO

This document tracks planned features, improvements, and known issues.

## v0.2.0 - Enhanced Content Management

### High Priority

- [ ] **Search functionality** - Full-text search across titles, summaries, and content
- [ ] **Filtering by topic** - Filter inbox by assigned topics
- [ ] **Sorting options** - Sort by date, title, status
- [ ] **Bulk actions** - Select multiple items for delete/reprocess
- [ ] **Offline mode** - Cache items locally for offline reading

### Medium Priority

- [ ] **Edit items** - Allow editing title and notes
- [ ] **Favorites/Bookmarks** - Mark important items
- [ ] **Reading progress** - Track read/unread status
- [ ] **Archive functionality** - Move items to archive instead of delete

## v0.3.0 - Collections & Organization

- [ ] **Collections/Folders** - Group items into custom collections
- [ ] **Tags** - User-defined tags in addition to AI topics
- [ ] **Smart collections** - Auto-collections based on rules
- [ ] **Drag & drop organization** - Reorder items within collections

## v0.4.0 - Enhanced AI Features

- [ ] **Custom prompts** - User-configurable summarization prompts
- [ ] **Multiple AI models** - Support different Ollama models per task
- [ ] **Key insights extraction** - Extract bullet points from content
- [ ] **Related content** - AI-powered content recommendations
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
