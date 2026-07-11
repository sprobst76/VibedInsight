# VibedInsight — Projektkontext für Claude

Self-hosted Personal-Knowledge-Plattform: URLs/Notizen sammeln, per Ollama
zusammenfassen und verschlagworten, Weekly-Digest, Knowledge-Graph.
Flutter-App (Android) + FastAPI-Backend + PostgreSQL (pgvector) auf dem VPS.

## Architekturentscheidungen (2026-07, bewusst getroffen)

- **Single-User + API-Key.** Die gesamte API ist durch einen statischen
  `X-API-Key`-Header geschützt (Middleware in `backend/app/main.py`, Key in
  `backend/.env` als `API_KEY`, in der App unter Einstellungen).
  Der frühere JWT-Auth-/verschlüsselte-Vault-Stack (PRIVACY_DESIGN_FINAL.md)
  wurde **entfernt** — er war nie mit dem Ingest-Flow verbunden, und
  Client-seitige Verschlüsselung widerspricht der Server-KI-Verarbeitung.
  Wiederherstellbar aus der Git-History (vor Commit "Simplify to single-user").
  Falls je Multi-User: normales Login auf UserItem-Basis nachrüsten, KEIN Vault.
- **raw_text wird behalten** (früher nach Processing gelöscht). Nötig für
  Reprocessing und künftiges RAG ("Frag dein Archiv").
- **Alembic ist die einzige Schema-Wahrheit.** Der Container-Entrypoint führt
  `python -m app.migrate` aus (erkennt auch Legacy-DBs ohne Stempel).
  `init_db()`/create_all ist nur Dev/Test-Komfort. NIE wieder Ad-hoc-ALTERs
  in init_db anhängen.
- **pgvector** (Image `pgvector/pgvector:pg16`) für Embedding-Similarity;
  Embeddings entstehen im Ingest-Flow (`app/services/processing.py`).
  Relations: SIMILAR (Embedding-Cosine ≥ 0.75) bevorzugt, RELATED
  (≥2 gemeinsame Topics) als Fallback.
- **LLM-Ausgaben über Ollama structured outputs** (`format=<JSON-Schema>` in
  `summarizer.py`) — kein Regex-Parsing von Freitext mehr. Topics werden auf
  Deutsch normalisiert (`normalize_topic`).
- Weekly-Digest wird sonntags 18:00 automatisch generiert
  (`app/services/scheduler.py`, abschaltbar via `WEEKLY_AUTO_GENERATE=false`).

## Stolperfallen

- Der API-Container hat **kein Host-Port-Mapping** (nur Traefik-Netz
  `ai-lab_ai-lab`). Health-Checks vom VPS-Host müssen per
  `docker compose exec api curl localhost:8000/health` laufen.
- FastAPI-Routen: `/items/bulk/*` MUSS vor `/items/{item_id}/...` deklariert
  bleiben, sonst fängt der int-Pfadparameter "bulk" ab (422).
- Flutter: `flutter analyze` schlägt auch bei Infos fehl → Deprecations sofort
  fixen. Drift-Schemaänderungen brauchen `schemaVersion`-Bump + `onUpgrade`
  + `dart run build_runner build`.
- Lokal gibt es kein Docker/Postgres — Backend-Tests laufen nur in CI
  (GitHub Actions mit pgvector-Service) oder gegen eine manuell erreichbare DB.
- Deploy: Push auf `main` → GitHub Action → SSH auf VPS → `deploy.sh update`.
  CI-Branchtests: Branches `rework/**` triggern CI ohne Deploy.

## Versionen

Eine Version für App + Backend, gepflegt in `app/pubspec.yaml`,
`backend/pyproject.toml` und `APP_VERSION` in `backend/app/main.py`;
CHANGELOG.md nachziehen.

## Offene Ideen (bewusst noch nicht gebaut)

Siehe TODO.md: RAG-Chat über gespeicherte Inhalte, Serendipity-Resurfacing,
KI-Triage auf Basis der Sterne-Ratings, Telegram-Bot/Bookmarklet als
Capture-Kanäle.
