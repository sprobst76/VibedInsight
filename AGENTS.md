# AGENTS.md — VibedInsight

## Ziel
VibedInsight ist eine persönliche Wissens-App zum Sammeln von Links/Newslettern/PDFs und Erzeugen von Themen-Zusammenfassungen.
MVP zuerst, später optional Graph/Neo4j.

## Stack-Entscheidungen (MVP)
- Backend: FastAPI (Python)
- UI: Streamlit (Python)
- Storage: PostgreSQL (Metadaten) oder SQLite im MVP
- Vektorsuche: Qdrant optional (erst ab Phase 2)
- LLM: Ollama lokal; optional Azure OpenAI als Provider

## Coding Standards
- Python: ruff + black
- Typing: mypy optional, aber saubere Typen
- Tests: pytest
- Keine unnötigen Abhängigkeiten
- Kleine, reviewbare Diffs (pro Task ein Commit)

## Arbeitsweise
1. Erst Plan (max 7 Schritte)
2. Dann minimaler Diff
3. Danach lokale Verifikation (lint/test/format)
4. Keine großen Refactors ohne expliziten Grund

