# Changelog

All notable changes to VibedInsight will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.5] - 2026-07-24

### Changed — Asynchrone Weekly-Generierung
- Die Digest-Generierung läuft jetzt als **Hintergrund-Task**; die Endpoints
  kehren sofort zurück und die App **pollt den Status**. Behebt den Timeout bei
  schweren Wochen (auf dem CPU-VPS dauerte ein Digest über ~26 Artikel ~9,5 min
  und lief in den synchronen Request-Timeout).
  - Backend: `POST /weekly/generate-current` und `POST /weekly/{id}/generate`
    liefern `{summary_id, status:"processing"}`; neuer
    `GET /weekly/{id}/generation-status` (`processing`/`completed`/`failed`/`idle`).
    Status in-memory (Single-User); ein Neustart setzt `idle` (aus dem
    gespeicherten Digest abgeleitet). Der Sonntags-Scheduler ist unberührt.
  - App: `generateCurrentWeekSummary`/`generateSummary` stoßen an und pollen
    alle 6 s bis `completed` (max. ~20 min), dann wird der Digest geladen.
    Hinweis im Leer-Zustand: „Das kann ein paar Minuten dauern".

## [0.6.4] - 2026-07-22 (Backend)

### Fixed — Audio-Digest Aussprache
- Eigennamen, die die deutsche Stimme verfehlt, werden phonetisch ersetzt
  (`_PRONUNCIATIONS` in `normalize_for_speech`): „Claude" → „Kload".
- Cache-Key um eine **Speech-Version** erweitert (`_SPEECH_CACHE_VERSION`),
  damit Änderungen an Prompt/Normalisierung gecachte Audio automatisch neu
  erzeugen statt eine ältere Fassung auszuliefern.

## [0.6.3] - 2026-07-22 (Backend)

### Changed — Audio-Digest: gesprochenes Skript statt Vorlesen (P13.6)
- Der Digest wird vor der Synthese per LLM (`qwen2.5`) in ein **Sprech-Skript**
  umgeschrieben (`prompts/podcast_script.txt`, `generate_podcast_script`):
  kurze gesprochene Sätze, keine Listen/Nummerierungen, Abkürzungen
  ausgeschrieben, englische Fachbegriffe vermieden. Fällt bei LLM-Fehler auf das
  wörtliche Vorlesen zurück. Abschaltbar via `audio_podcast_script=false`.
- **`normalize_for_speech`**: entfernt URLs/Markdown/Listen-Marker und schreibt
  gängige Abkürzungen aus (`z. B.` → „zum Beispiel", `AI` → „künstliche
  Intelligenz" …) — behebt die schlimmsten Aussprache-Patzer der kleinen Stimme.
- Cache-Key enthält jetzt den Skript-Modus (`pod`/`plain`), damit ein
  Moduswechsel keine veraltete Audio ausliefert. Piper-Synthese läuft nun in
  einem Thread (blockiert den Event-Loop nicht mehr).
- _Grenze:_ Die Qualität hängt am kleinen CPU-Modell (`qwen2.5:3b` auf dem VPS)
  — deutlich gesprochener als vorher, aber Deutsch/Fachbegriffe bleiben nicht
  perfekt. Besseres Modell = mehr VPS-RAM.

## [0.6.2] - 2026-07-22

### Added — Audio-Digest Drill-down (P13.5)
- **„Mehr dazu — im Archiv nachfragen"** unter dem Wochen-Digest: öffnet den
  RAG-Chat mit einer aus dem Digest abgeleiteten Frage (Top-Themen der Woche,
  Fallback TL;DR) und **schickt sie automatisch** ab. Das ist das
  Alleinstellungsmerkmal gegenüber NotebookLM: Der Digest ist kein Dead-End,
  sondern der Einstieg ins eigene, durchsuchbare Archiv — mit antippbaren
  Quellen aus der RAG-Antwort.
- `ChatScreen(initialQuestion:)` + Route `/chat?q=…` (auto-send beim Öffnen).

## [0.6.1] - 2026-07-22

### Fixed
- **Weekly-Screen Leer-Zustand**: Der Button „Zusammenfassung erstellen" hing an
  `itemsProcessed > 0`, was aber erst *nach* der Generierung > 0 wird — bei einer
  frischen Woche mit Artikeln erschien der Button daher nie. Jetzt an
  `itemsCount > 0` geknüpft. (Aufgefallen beim Audio-Digest-Test: ohne Digest
  keine Audio-Karte.)

### Known
- **Weekly-Generierung ist bei vielen Items langsam** (CPU-VPS): ein Digest über
  ~26 Artikel überschreitet einen synchronen Request (>280 s Prompt-Eval). Der
  „generieren"-Button kann dadurch ins Timeout laufen. Folgeaufgabe: Generierung
  asynchron (Background-Job + Polling wie Reprocess). Betrifft das Weekly-Feature
  generell, nicht nur Audio.

## [0.6.0] - 2026-07-22

### Added — Audio-Digest App-Playback (P13.4)
- **Play-Button + Inline-Player** im Wochenrückblick (`weekly_screen`): lädt das
  Audio lazy beim ersten Tap (Backend synthetisiert einmal + cacht), spielt via
  `just_audio` mit Play/Pause, Position-Slider und Zeitanzeige. Der Button
  erscheint nur, wenn das Backend TTS kann (`GET /audio/status`, neuer
  `audioAvailableProvider`); fehlt es, degradiert der Player zu einer
  Fehlerzeile mit „Erneut".
- `ApiClient.downloadWeeklyAudio` (Temp-Datei je Digest) + `audioAvailable`.
- App-Version **0.6.0+24**.

### Added — Audio-Digest MVP (P13, Backend)
- **`GET /audio/weekly/{id}`**: gibt den vorhandenen Weekly-Digest als
  gesprochenes Audio aus (MP3 wenn ffmpeg da, sonst WAV). Kein Extra-LLM-Call —
  der Digest-Text wird zu natürlicher Sprache zusammengesetzt
  (`build_digest_script`) und **auf Disk gecacht** (Key = Digest-`generated_at`),
  also max. einmal pro Digest synthetisiert.
- **TTS via Piper** (`app/services/audio.py`, Stimme `de_DE-thorsten-medium`,
  in den Docker-Build gebacken, ~61 MB; nicht in git). Lazy-geladen, gecacht.
- **`GET /audio/status`**: meldet, ob TTS verfügbar ist (App kann den
  Play-Button ausblenden). Fehlt Piper/Voice → Endpoints degradieren zu 503.
- **`POST /admin/audio/benchmark`**: misst On-Box-TTS-Latenz per curl — direkt
  auf dem VPS ausführbar, ohne SSH.

### Performance
- Lokaler Spike (P13.1): ~59 s Sprache in ~2 s (RTF ~0,03, ~30× Echtzeit).
- **On-VPS gemessen** (P13.3, 4 Kerne/7,6 GB, CPU-only): **RTF ~0,11 =
  ~9× Echtzeit** steady state (~5× inkl. einmaligem Modell-Laden). Ein
  4-Minuten-Digest wäre damit in ~26 s synthetisiert — und nur einmal, danach
  Disk-Cache. TTS ist **nicht** der Flaschenhals (anders als die RAG-Prompt-Eval
  mit ~80 s). End-to-End verifiziert: `/audio/weekly/3` → 200 audio/mpeg 341 KB.

### Notes
- **Nächste Schnitte:** „Mehr dazu"→RAG-Chat-Drilldown (P13.5) und optionaler
  Podcast-Skript-Generator (P13.6).
- Docker-Image wächst ~300 MB (onnxruntime + ffmpeg + Voice) — bewusst
  akzeptiert für die Self-hosted-Single-User-App.
- On-Device-Audibilität ist UAT nach dem Play-Release (lokales Debug-APK lässt
  sich wegen Play-Signatur nicht über die installierte Version legen).

## [0.5.3] - 2026-07-20

### Added — KI-Triage der Inbox (P4)
- **triage_score** (neue Spalte `user_items.triage_score`, Migration 008): beim
  Ingest bekommt jedes Item einen Score = max. Cosine-Similarity seines
  Embeddings zu den **hoch-bewerteten** Items des Nutzers (Rating ≥
  `triage_min_rating`, Default 4). „Ähnelt etwas, das dir gefallen hat."
- **`POST /admin/retriage`**: rechnet alle Scores neu (Backfill, nach
  Rating-Änderungen). Sort `?sort_by=triage` (nulls last) sortiert die Inbox
  nach Relevanz.
- **App**: Sort-Option „Für dich" (Triage) + Blitz-Indikator auf Karten mit
  hohem Score (≥ 0.6). Backend-Tests (ähnlich → hoch, unähnlich → niedrig).

_Aktiv, sobald der Nutzer Items mit 4–5 Sternen bewertet (Trainingssignal)._

## [0.5.2] - 2026-07-20

### Added — Serendipity-Resurfacing „Wiederentdeckt" (P3)
- **`GET /resurface`**: liefert ein gewichtet-zufälliges altes, ungelesenes,
  nicht-archiviertes Item (älter = wahrscheinlicher; Mindestalter konfigurierbar
  via `resurfacing_min_age_days`, abschaltbar via `resurfacing_enabled`).
- **App**: „Wiederentdeckt"-Banner in der Inbox (antippbar → öffnet das Item,
  wegwischbar) plus eine **lokale Notification** (max. 1×/Tag) beim App-Start,
  wenn ein Item hochgespült wird.
- **Notification-Tap-Handler verdrahtet** (war ein leerer Stub): Tap navigiert
  jetzt zum Ziel — Item-ID → Detail, `weekly:<id>` → Wochen-Digest — sowohl im
  laufenden Betrieb als auch beim Kaltstart aus einer Notification
  (`utils/notification_routes.dart`, unit-getestet).

## [0.5.1] - 2026-07-20

### Added — RAG-Streaming
- **`POST /chat/stream`**: NDJSON-Event-Stream (`sources` → `delta`* → `done`,
  bzw. `answer` im Kein-Kontext-Fall, `error` bei Fehlern). Das Retrieval
  (DB-gebunden) läuft vor dem Stream, gestreamt wird nur die Ollama-Generierung
  (`ollama_chat_stream`) — die DB-Session wird nie mitten im Stream benutzt.
- **App streamt die Antwort**: Quellen-Chips erscheinen sofort (~5s), die
  Antwort läuft Token für Token ein statt eingefrorenem Warten. `ApiClient
  .chatStream` (byte-basiertes NDJSON-Parsing), Provider aktualisiert die
  Assistant-Bubble inkrementell. Backend- + Provider-Tests.

_Hinweis: Auf CPU-Servern dominiert die Prompt-Evaluation die Zeit bis zum
ersten Token; Streaming verbessert v.a. die gefühlte Latenz (Quellen sofort,
sichtbarer Fortschritt)._

## [0.5.0] - 2026-07-20

### Added — RAG-Chat „Frag dein Archiv" (P2)
- **`POST /chat`**: Frage → Embedding → pgvector-Cosine-Top-K über die
  gespeicherten Item-Embeddings → nummerierter, budgetierter Kontext → Ollama
  antwortet auf Deutsch, geerdet in den Quellen (Zitate `[n]`). Quellen werden
  deterministisch aus dem Retrieval abgeleitet (nicht aus der Modellausgabe)
  und sind user-scoped — die Quellen-`id` ist die `UserItem.id`, sodass die App
  direkt zum Item springen kann. Kein-Kontext-Fall antwortet klar und ruft das
  LLM nicht auf. Für CPU-only-Deployments latenz-getunt: `rag_top_k=4`,
  Kontext-Budget 3000 Zeichen, Antwortlänge via Ollama `num_predict=200`
  gecappt (`rag_min_similarity=0.2`). Backend-Tests + End-to-End gegen prod
  verifiziert.
- **Chat-Screen in der App** („Frag dein Archiv", Icon in der Inbox-AppBar):
  Konversations-UI mit Frage-/Antwort-Bubbles, Typing-Indikator, Fehler-Bubble
  und antippbaren Quellen-Chips `[n] Titel` → öffnen das jeweilige Item.
  Lokalisiert (de/en); Provider unit-getestet.

## [0.4.5] - 2026-07-20

### Fixed
- **Stale-ApiClient-Bug**: Nach dem Eintragen/Ändern von Server-URL oder API-Key
  in den Einstellungen blieb die Inbox leer, bis die App neu gestartet wurde.
  Der `ItemsNotifier` lädt jetzt beim Erzeugen selbst (und wird bei
  Settings-Änderung neu erzeugt) → geänderte Verbindungsdaten greifen sofort.
  `mounted`-Guards verhindern „use after dispose" bei schnellen Rebuilds.
- **Lange URLs** in Item-Cards liefen aus der Zeile (RenderFlex-Overflow); die
  Quelle wird jetzt einzeilig mit Ellipsis abgeschnitten.

### Added (App-Qualität, P7)
- **Loading-Skeletons** statt nacktem Spinner beim ersten Laden der Liste.
- **Freundliche Fehler-UX**: API-Fehler werden übersetzt (Key ungültig /
  Server nicht erreichbar / Server-Fehler) mit „Erneut versuchen" und — bei
  Key-Fehlern — Direktlink in die Einstellungen (`utils/error_messages.dart`,
  unit-getestet).
- **Settings-Verbindungstest** prüft jetzt Erreichbarkeit UND Key-Gültigkeit
  getrennt (`ApiClient.checkAuth` gegen einen geschützten Endpunkt), statt nur
  das public `/health` — ein falscher Key wird sofort erkannt.
- **Tests**: ItemsNotifier-Unit-Tests (Auto-Load, Fehler, Pagination, Toggle,
  Suche) gegen Mock-API + In-Memory-Drift; Integrationstests komplett neu
  geschrieben (hermetisch, echte Assertions statt `if isNotEmpty`-Scheinabdeckung)
  — deckten einen realen Isolationsbug auf (globaler GoRouter behielt seine Route
  zwischen Tests → jetzt zurücksetzbar). ~90 Host-Tests + 6 Device-Integrationstests.
- **Performance**: `pageSize` zentralisiert (`ApiConfig`); Inbox lädt Seiten
  inkrementell über virtualisierte `ListView.builder` (Pagination-Test).
- **Accessibility**: Favorit/Gelesen als `IconButton` (44dp-Touch-Target +
  Screenreader-Tooltip statt bloßer `GestureDetector`), Sterne mit Semantics-Label.
- **i18n-Gerüst**: `flutter_localizations` + gen-l10n (de/en), Delegates verdrahtet,
  Kern-Strings der Inbox lokalisiert (`lib/l10n/app_{de,en}.arb`).

## [0.4.4] - 2026-07-20

### Added
- **Öffentlicher `/privacy`-Endpoint** (DE+EN, ohne API-Key erreichbar) als
  Datenschutz-URL für den Play-Store-Eintrag.
- **Play-Store-Release-Pipeline**: `git tag v*` baut ein signiertes AAB, hängt es
  ans GitHub-Release und lädt es (Service-Account-Secret gesetzt) automatisch in
  den Play-Internal-Track.

## [0.4.3] - 2026-07-19

### Fixed
- **Topics mit Unterstrichen** (z.B. `sarah_joepgen`) durch das kleinere
  `qwen2.5:3b`: `topics.txt` schärft die Regeln (natürliche Wörter, keine
  Unterstriche) und `normalize_topic` ersetzt Unterstriche deterministisch
  durch Leerzeichen — modellunabhängige Garantie.

### Changed
- **`datetime.utcnow()` entfernt** (Python-3.12-Deprecation): neuer
  `app/timeutils.py`-Helper `utcnow()` liefert naives UTC (gleiche Semantik wie
  bisher, da die DateTime-Spalten naiv sind — kein aware/naive-Mischbruch).
  Alle 13 App-Fundstellen umgestellt; Tests laufen jetzt ohne Deprecation-Warnings.

## [0.4.2] - 2026-07-19

### Fixed
- **Topics akkumulierten beim Reprocessing**: `_attach_topics` hängte neue
  Topics nur an, ohne alte zu entfernen — nach einem Reprocess hatte ein Item
  die alten *und* neuen Topics (inkl. alter englischer). Ersetzt jetzt (clear
  vor attach). Verifiziert: Dev-Item 3 → 3 Topics vor und nach Reprocess.
- **Summary-Format bei kleinen Modellen**: `qwen2.5:3b` (Prod) formatierte mit
  `### Überschriften` / `**Stichpunkt 1:**`. Prompt schärft jetzt das Format
  (reine `- `-Bullets, keine Header/Nummerierung/Fettschrift). Verifiziert
  gegen qwen2.5:3b.

### Changed
- **Prod-Chat-Modell `llama3.2:1b` → `qwen2.5:3b`** (VPS CPU-only, 7,6 GB RAM;
  deutlich besseres Deutsch + strukturierte Ausgabe, sicherer RAM-Footprint).

## [0.4.1] - 2026-07-19

### Fixed
- **Summaries jetzt immer auf Deutsch**: Der `summary`-Prompt
  (`backend/app/prompts/summary.txt`) war komplett englisch und erzwang keine
  Ausgabesprache — dadurch kamen Zusammenfassungen häufig englisch, selbst bei
  deutschem Input. Prompt auf Deutsch umgeschrieben und "ausschließlich auf
  Deutsch" erzwungen (verifiziert: deutsches *und* englisches Item → beide
  Summaries deutsch).

### Added
- **`IMPLEMENTATION-PLAN.md`**: Arbeitspakete (Doku-Drift, Ollama-Update,
  Modellwechsel) mit Modell-Vorauswahl je Aufgabe (Token-Optimierung).
- **CLAUDE.md**: Abschnitt "Arbeitsweise: Modell-Routing" + Stolperfalle
  "Prod-Daten sind das Original".
- **SECURITY.md**: Abschnitt "Operational Practices" (Backups, Restore-Test,
  API_KEY, Secret-Handling).

### Changed
- Doku an den pop-os-Dev-Standort angepasst (CLAUDE.md/DEV.md/MIGRATION.md):
  Docker/Compose lokal vorhanden, Flutter unter `~/flutter/bin`, Ollama als
  Container.

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
