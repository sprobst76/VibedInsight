# VibedInsight — Projektkontext für Claude

Self-hosted Personal-Knowledge-Plattform: URLs/Notizen sammeln, per Ollama
zusammenfassen und verschlagworten, Weekly-Digest, Knowledge-Graph.
Flutter-App (Android) + FastAPI-Backend + PostgreSQL (pgvector) auf dem VPS.

## Dev-Umgebung (Stand 2026-07-19)

Entwicklung läuft auf dem **development-homeserver** (Tailscale
`development-homeserver`; Docker, Ollama, Test-Smartphone per USB) — siehe
`DEV.md`. Auch auf **pop-os** (lokaler Dev-Rechner) läuft der gleiche Stack
mit den gleichen Ports (:8100 API, :5433 pgvector). Dev-Stack: `./dev.sh up`
(API mit --reload, pgvector, eigene Test-DB für pytest via `./dev.sh test`).
Git/GitHub ist die einzige Quelle der Wahrheit — NIE Projektbäume per rsync
syncen. Prod-Deploy bleibt unverändert: Push auf `main` → VPS.

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

## Arbeitsweise: Modell-Routing (Token-Vorauswahl)

Bei Implementierungsplänen trägt jede Aufgabe ein Modell-Etikett — das
schwächste noch ausreichende Modell, einmalig strategisch festgelegt.
Ausführung liest das Etikett nur ab: "einmal teuer denken, oft billig
ausführen".

| Modell | Wofür |
|---|---|
| Haiku 4.5 | Klare, repetitive Arbeit: Doku, Prompt-Text, Boilerplate, mechanische Fixes |
| Sonnet 5 | Standard-Entwicklung: Code mit Logik, Integration, Tests, Docker/Compose |
| Opus 4.8 | Algorithmen, kniffliges Denken, heikle Migrationen |
| Fable 5 | Strategie/Design/Konzept-Weichen (z.B. Planerstellung) |
| ? Nachfragen | Scope/Entscheidung offen — erst fragen/messen, dann ausführen |

Faustregel: Billigstes Modell, das die Aufgabe noch zuverlässig löst;
hochstufen, sobald echte Logik/Strategie ins Spiel kommt.
Lebendes Beispiel: `IMPLEMENTATION-PLAN.md`.

## Prod-Setup (Stand 2026-07-19)

- **VPS-Chat-Modell: `qwen2.5:3b`** (seit 2026-07-19; vorher `llama3.2:1b` —
  zu schwach). VPS hat 7,6 GB RAM / 4 Kerne / CPU-only und swappt schon → auf
  `qwen2.5:3b` (bereits gepullt, gutes Deutsch + JSON) statt `qwen3:4b-instruct`
  (bräuchte mehr RAM). Embedding bleibt `mxbai-embed-large` (1024-dim, fix).
  VPS-Ollama gepullt: `llama3.2:1b/3b`, `qwen2.5:3b`, `mxbai-embed-large`,
  `nomic-embed-text`. Backend pullt fehlende Chat-Modelle sonst automatisch nach.
- Ollama auf dem VPS ist Teil des geteilten `ai-lab`-Stacks (wie auf pop-os).
- `API_KEY` ist auf dem VPS **gesetzt** (seit 2026-07-19) — API ist geschützt:
  `/items` ohne `X-API-Key` → 401, mit Key → 200. Denselben Key trägt die App
  unter Einstellungen. **Achtung:** `.env`-Key-Änderung braucht `docker compose
  up -d` (recreate), nicht `restart`.
- Diagnose ohne SSH: `GET /admin/ollama/check`, `GET /admin/stats`,
  `GET /admin/reprocess-status/<batch_id>`.

## Stolperfallen

- Der API-Container hat **kein Host-Port-Mapping** (nur Traefik-Netz
  `ai-lab_ai-lab`). Health-Checks vom VPS-Host müssen per
  `docker compose exec api curl localhost:8000/health` laufen.
- **`.env`-Änderungen brauchen `docker compose up -d` (recreate), NICHT
  `deploy.sh restart`.** `docker compose restart` startet nur den bestehenden
  Container neu und liest das `env_file` NICHT neu ein — z.B. ein geändertes
  `OLLAMA_MODEL` greift erst nach `up -d`. (Verifiziert 2026-07-19 beim
  VPS-Modellwechsel.)
- FastAPI-Routen: `/items/bulk/*` MUSS vor `/items/{item_id}/...` deklariert
  bleiben, sonst fängt der int-Pfadparameter "bulk" ab (422).
- Flutter: `flutter analyze` schlägt auch bei Infos fehl → Deprecations sofort
  fixen. Drift-Schemaänderungen brauchen `schemaVersion`-Bump + `onUpgrade`
  + `dart run build_runner build`.
- Der lokale Dev-Rechner (pop-os) ist inzwischen vollwertiger zweiter Dev-Standort:
  Docker 29.6.1 + Compose vorhanden, `./dev.sh up` läuft end-to-end (verifiziert
  2026-07-19), Backend-Tests lokal via `./dev.sh test`. CI (GitHub Actions mit
  pgvector) bleibt für Branch-Tests. (Der Homeserver bleibt der primäre Dev-Standort
  — siehe `DEV.md`.)
- **Prod-Daten sind das Original.** Die VPS-Postgres ist die einzige Quelle der
  echten Inhalte — NIE mit leerem/altem Dev-Stand überschreiben. Datenfluss nur
  Prod→Dev (z.B. `pg_dump` vom VPS in die Dev-DB), nie umgekehrt. Vor riskanten
  Prod-Aktionen `./deploy.sh backup`.
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
