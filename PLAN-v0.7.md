# Umsetzungsplan v0.7: Robustheit, Capture, Embeddings, Watchlist (2026-10-14)

Quelle: Analysebericht vom 2026-10-14 (Session-Scratchpad `improvement-report.md`, Stand v0.6.5).
Format und Methode wie in `IMPLEMENTATION-PLAN.md`: Jede Aufgabe trägt das **schwächste noch
ausreichende** Modell. Eine Aufgabe ist ≤ ~1 h und einzeln committbar. Wenn sich eine Aufgabe als
schwerer herausstellt, wird sie hochgestuft und das Etikett hier nachgezogen.

| Modell | Wofür (in diesem Plan) |
|---|---|
| **Haiku 4.5** | Doku, Prompt-Text, Boilerplate, mechanische Fixes, Tests nach vorhandener Vorlage, adb/curl-Verifikation |
| **Sonnet 5.5** | Standard-Code mit Logik, Integration, neue Tests, rein additive Alembic-Migrationen (nur neue Spalten/Indizes) |
| **Opus 5.5** | SSRF/Security, datenverändernde oder Enum-Migrationen, Embedding-Wechsel, Kalibrierung, Relevanz-Algorithmus |
| **Fable 5.1** | Nur Design-Weichen: Watchlist-Konzept, Relevanz-Gate-Konzept |
| **? / Stefan** | Entscheidung offen, SSH/VPS, Gerät in der Hand |

**Code-Verifikation vor der Planung** (2026-10-14, alle Punkte bestätigt):
- `routers/ingest.py:42-46`: `normalize_url` verwirft Query und Fragment.
- `services/extractor.py:28-57`: `getaddrinfo` läuft synchron und prüft nur den ersten Host; dazu `follow_redirects=True`, kein Größenlimit, `trafilatura` synchron.
- `num_ctx` kommt im ganzen Backend nicht vor (`grep` leer). Durchreichen geht trotzdem einfach, weil `summarizer.py:107,139` schon einen `options`-Parameter hat.
- Weekly nimmt `items_content[:20]` unsortiert (`summarizer.py:288`).
- Topics entstehen per `Topic(name=…)` ohne `ON CONFLICT` (`processing.py:197`).
- Share-Intent: `SystemNavigator.pop()` (`share_intent_provider.dart:102`) läuft **vor** `apiClient.ingestUrl` (`:107`).

**Querschnittsregeln**:
- **Branches:** Pro Phase `rework/v0.7-<phase>`; CI läuft dort ohne Deploy. Merge auf `main` bedeutet Prod-Deploy.
- **Schema:** Alembic ist die einzige Schema-Wahrheit; nächste freie Nummer ist `009`.
- **Tests:** laufen über `./dev.sh test` gegen die eigene Test-DB.
- **Release:** Version an 3 Stellen (`app/pubspec.yaml`, `backend/pyproject.toml`, `APP_VERSION` in `backend/app/main.py`) und `CHANGELOG.md`.
- **Prod:** Vor jeder datenverändernden Prod-Aktion `./deploy.sh backup` (macht Stefan).

---

## Phase A: Backend-Bugs (sofort startbar)

Die Blöcke A1, A2 und A3 sind **voneinander unabhängig** und laufen parallel, z. B. in getrennten
Worktrees. A4 braucht A1.1, weil `ON CONFLICT` auf dem neuen Hash aufsetzt.

### A1: URL-Normalisierung und Rehash

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| A1.1 | Neue `normalize_url` schreiben. Sie behält den Query-String, sortiert die Parameter, entfernt Tracking-Parameter (`utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`, `ref_src`, `si`), das Fragment und den Default-Port und senkt Scheme und Host auf Kleinbuchstaben. Den Slash-Fix beibehalten. Die Funktion nach `services/urlnorm.py` verschieben, weil der Watchlist-Code sie mitbenutzt. | Sonnet | `backend/app/services/urlnorm.py` (neu), `routers/ingest.py` (Import) | — | Kanonisierungsregeln mit Randfällen |
| A1.2 | Tabellengetriebene Tests: YouTube `?v=A` und `?v=B` ergeben verschiedene Hashes; `utm_` wird entfernt; die Reihenfolge der Parameter ist egal; `#frag` wird entfernt; `HTTP://X.de:80/a/` wird zu `http://x.de/a`. | Haiku | `backend/tests/test_urlnorm.py` | A1.1 | Fälle stehen fest, mechanisch |
| A1.3 | **Rehash im Dry-Run** als CLI `python -m app.tools.rehash --dry-run`. Es berechnet für alle `content_items` den neuen Hash und meldet: Anzahl geänderter Hashes, **Kollisionen** (zwei Items bekämen denselben neuen Hash) mit IDs. Es schreibt nichts. | Opus | `backend/app/tools/rehash.py` (neu) | A1.1 | Arbeitet auf Prod-Daten, Kollisionslogik muss stimmen |
| A1.4 | **Rehash mit `--apply`**. Alles läuft in einer Transaktion. Bei einer Kollision bleibt das älteste Item kanonisch. Jüngere Items werden **nicht gelöscht**: Ihr `url_hash` wird auf `<neu>:dup:<id>` gesetzt, und sie werden geloggt. Danach `--report` als CSV. Idempotent. **Kein Alembic-Schritt**, deshalb ist der Rehash separat schaltbar und läuft nicht automatisch beim Container-Start. | Opus | `tools/rehash.py`, `backend/tests/test_rehash.py` | A1.3 | Prod-Daten dürfen nie verloren gehen; Ausweichschema für Duplikate |
| A1.5 | Doku-Rezept: `./deploy.sh backup`, dann `docker compose exec api python -m app.tools.rehash --dry-run`, dann (nach Stefans Freigabe) `--apply`. Hinweis: Früher fälschlich weg-dedupte URLs (das zweite Video) sind **nicht wiederherstellbar** und müssen neu geteilt werden. | Haiku | `DEV.md` (Ops-Abschnitt) | A1.4 | Rezept abschreiben |

**Tests A1:**
- Fixture mit 3 Items: zwei kollidieren, eines ändert sich nicht. Nach `--apply` sind alle drei Items noch vorhanden, und genau eines hat den kanonischen Hash.
- Ein zweiter Lauf ändert nichts mehr.

**Akzeptanz A1:** Der Dry-Run auf einem Prod-Dump in der Dev-DB läuft ohne Fehler und gibt einen Kollisionsbericht aus.

### A2: SSRF-sicherer Fetcher

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| A2.1 | `services/fetcher.py` mit `safe_fetch(url, *, max_bytes, accept, etag, last_modified)`:<br>• DNS async über `loop.getaddrinfo`.<br>• Alle IPs werden geprüft (private, loopback, link-local, reserved, multicast, IPv4-mapped IPv6, `0.0.0.0/8`, CGNAT `100.64/10`).<br>• **IP-Pinning:** Verbindung zur geprüften IP über einen eigenen `httpx`-Transport, mit `Host`-Header und SNI = Hostname.<br>• `follow_redirects=False` mit manueller Schleife (max. 5), jeder Hop wird neu geprüft; nur `http`/`https`.<br>• `ALLOW_PRIVATE_URLS` bleibt als Dev-Schalter erhalten. | Opus | `backend/app/services/fetcher.py` (neu) | — | Security-kritisch (Rebinding/TOCTOU, Redirect-Bypass) |
| A2.2 | Streaming mit Größenlimit (`fetch_max_bytes`, Default 5 MB, Abbruch beim Überschreiten). Content-Type-Allowlist (`text/html`, `application/xhtml+xml`, `text/plain`; Feeds kommen später in D6). Rückgabe als Dataclass (`status`, `final_url`, `headers`, `body`, `etag`). Konfiguration über `config.py`. | Sonnet | `fetcher.py`, `config.py` | A2.1 | Standardlogik auf fertigem Gerüst |
| A2.3 | Tests mit `respx` oder einem Fake-Resolver:<br>• 302 auf `127.0.0.1`, `169.254.169.254`, `[::1]` und `[::ffff:127.0.0.1]` wird abgelehnt.<br>• Rebinding (der Resolver liefert beim zweiten Aufruf eine private IP) wird abgelehnt, weil gepinnt ist.<br>• Mehr als 5 MB wird abgebrochen; `image/png` wird abgelehnt; mehr als 5 Redirects wird abgebrochen. | Sonnet | `backend/tests/test_fetcher.py` | A2.2 | Fehlerpfade gezielt bauen |
| A2.4 | `extractor.py` auf `safe_fetch` umstellen. `trafilatura.extract` und `extract_metadata` laufen per `asyncio.to_thread`. Den alten `_check_url_allowed` entfernen. | Haiku | `services/extractor.py` | A2.2 | Mechanischer Umbau |
| A2.5 | Kurzes Security-Review des Diffs A2.1 bis A2.4 gegen die Checkliste oben (Skill `security-review`). | Opus | — | A2.4 | Zweiter Blick bei Security lohnt sich |

**Akzeptanz A2:**
- Alle Tests aus A2.3 sind grün, und die bestehenden Ingest-Tests sind grün.
- Manueller Dev-Ingest einer echten Seite funktioniert.
- Parallel zu einem großen Ingest antwortet ein Chat-Stream weiter, der Event-Loop ist also nicht blockiert.

### A3: Kontextfenster und Weekly

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| A3.1 | `ollama_num_ctx` einführen (Default 8192, per env übersteuerbar). Es wird in **alle** `generate`/`chat`-Aufrufe als `options={"num_ctx": …}` gemergt (Summary, Topics, Weekly, Audio-Script, RAG). | Haiku | `config.py`, `services/summarizer.py`, `services/rag.py` | — | `options` ist schon vorhanden, mechanisch |
| A3.2 | Erkennung von Abschneiden: Aus der Ollama-Antwort `prompt_eval_count` lesen. Liegt der Wert bei ≥ 95 % von `num_ctx`, ein Warning mit Item-ID loggen. Zusätzlich vorher eine grobe Zeichenschätzung (`len/3.5`) und den Text auf das Budget kürzen, statt Ollama still abschneiden zu lassen. | Sonnet | `summarizer.py` | A3.1 | Budgetrechnung |
| A3.3 | Weekly priorisieren: Items sortieren nach `rating desc`, dann `triage_score desc`, dann `created_at desc`, erst danach die Obergrenze anwenden. Die Obergrenze wird konfigurierbar (`weekly_max_items`). | Sonnet | `routers/weekly.py`, `summarizer.py:288` | — | Query mit Join auf `user_items` |
| A3.4 | Prompt `weekly_cluster.txt` (deutsch, JSON-Schema mit `theme`, `summary`, `key_points`) für den Map-Schritt. | Haiku | `backend/app/prompts/weekly_cluster.txt` | — | Reiner Prompt-Text |
| A3.5 | **Map-Reduce**: Items nach Top-Topic gruppieren (max. 6 Cluster, Rest in „Sonstiges“). Map: pro Cluster ein LLM-Call mit Budget. Reduce: der bestehende Weekly-Prompt bekommt die Cluster-Summaries statt Rohtext. Status-Polling (v0.6.5) zeigt den Fortschritt `cluster i/n`. | Sonnet | `summarizer.py`, `routers/weekly.py` | A3.1, A3.3, A3.4 | Integration in den Async-Flow |
| A3.6 | Tests: Die Sortierung stimmt. Map-Reduce mit gemocktem Ollama (3 Cluster ergeben 3 Map-Calls und 1 Reduce-Call). `num_ctx` steht in allen Calls (Mock prüft `options`). | Sonnet | `tests/test_weekly_async.py`, `tests/test_summarizer.py` | A3.5 | Neue Mock-Szenarien |

**Akzeptanz A3:**
- Dev-Digest über mehr als 20 Items läuft durch, und Items mit hohem Rating erscheinen sicher darin.
- Im Ollama-Log steht `n_ctx = 8192`.
- Laufzeit auf dem VPS notieren (vorher etwa 9,5 min); Map-Reduce darf sie höchstens um ~30 % verlängern, sonst die Cluster-Zahl senken.

### A4: Asynchroner Ingest, Retry-Felder, ON CONFLICT

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| A4.1 | Alembic **`009_processing_retry`**: `content_items.attempts int not null default 0`, `last_error text null`, `next_retry_at timestamptz null` mit Index. Rein additiv, mit Downgrade. Models nachziehen. | Sonnet | `alembic/versions/009_*.py`, `models/content.py` | — | Nur neue Spalten, kein Datenumbau |
| A4.2 | `ON CONFLICT` für Topics: `pg_insert(Topic).on_conflict_do_nothing(index_elements=["name"])`, danach `SELECT`. | Sonnet | `services/processing.py:~197`, Topic-Helfer | — | Race-Fix |
| A4.3 | `ON CONFLICT` für `url_hash` im Ingest: Bei parallelem Doppel-Ingest kommt 200 mit dem bestehenden Item statt 500. | Sonnet | `routers/ingest.py` | A1.1 | Baut auf dem neuen Hash auf |
| A4.4 | **Ingest wird asynchron.** `POST /ingest/url` legt das Item sofort an (`status=PENDING`, `url`, `title=url`) und antwortet **202** mit dem Item. Fetch, Extract und Processing laufen im Hintergrund-Task mit gehaltener Task-Referenz. Ein Extraktionsfehler setzt `FAILED`, `last_error` und `attempts+1`; das Item bleibt erhalten. | Sonnet | `routers/ingest.py`, `services/processing.py` | A4.1, A4.3 (A2.4 empfohlen) | Kernumbau des Flows |
| A4.5 | Retry-Tick: Die vorhandene Scheduler-Schleife holt alle 5 min Items mit `FAILED`, `attempts < 5` und `next_retry_at <= now` (`FOR UPDATE SKIP LOCKED`, Limit 3). Backoff ist `5 min · 2^attempts` (max. 12 h). Neuer Endpunkt `POST /items/{id}/retry` (setzt den Zähler zurück), deklariert **vor** `/items/{item_id}/...`-Routen mit int-Parameter. | Sonnet | `services/scheduler.py`, `routers/user_items.py` oder `items.py` | A4.4 | Scheduler-Integration |
| A4.6 | `attempts` und `last_error` in die Item-Response-Schemas aufnehmen. | Haiku | `schemas.py` | A4.1 | Boilerplate |
| A4.7 | Tests:<br>• Zwei gleichzeitige `process` mit demselben neuen Topic ergeben beide `COMPLETED`.<br>• Zwei gleichzeitige Ingests derselben URL ergeben 1 Item und keinen 500.<br>• Ein Fetch-Fehler ergibt ein Item in `FAILED` mit `last_error` und URL.<br>• Der Retry-Tick hebt `attempts`.<br>• `/items/bulk/*`-Routing ist nicht kaputt. | Sonnet | `tests/test_ingest.py` (neu), `tests/test_processing.py` (neu) | A4.2–A4.5 | Nebenläufigkeitstests mit `asyncio.gather` |
| A4.8 | App: 202/`PENDING` verarbeiten (Item sofort in der Liste, Status-Polling gibt es schon). Im Item-Detail `last_error` anzeigen plus Button „Erneut versuchen“. `flutter analyze` muss sauber sein. | Sonnet | `app/lib/…/api_client.dart`, Item-Detail-Screen, Model | A4.6 | UI und Netz |
| A4.9 | Release 0.7.0: Version an 3 Stellen und `CHANGELOG.md` (A1 bis A4). | Haiku | 3 Versionsstellen, `CHANGELOG.md` | A1–A4 | Mechanisch |

**Verifikation Phase A:**
- `./dev.sh test` grün, CI auf `rework/v0.7-a` grün.
- Dev-Roundtrip:
  - Paywall-URL ergibt ein `FAILED`-Item mit Grund.
  - YouTube `?v=A` und `?v=B` ergeben 2 Items.
  - Ein Doppel-Share ergibt 1 Item.
- App-Build auf dem Defy per adb installieren und einen Share testen.
- Nach dem Merge (Prod) über `/admin/stats` und einen Prod-Ingest ohne SSH prüfen.
- Danach Rehash per A1.5, ausgeführt von Stefan.

---

## Phase B: Share-Intent, Offline-Queue, WorkManager

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| B1 | `workmanager` als Abhängigkeit hinzufügen, Android-Init (Callback-Dispatcher) einrichten; die Builds `flutter analyze` und `flutter build apk` laufen. | Sonnet | `pubspec.yaml`, `main.dart`, `android/` | — | Plugin-Setup mit Isolate-Fallen |
| B2 | Share-Pfad: URL **in die `PendingActions`-Queue** von drift schreiben (`items_repository.dart:253`), **danach** `SystemNavigator.pop()`. Braucht der Queue-Eintrag einen neuen Typ, gelten `schemaVersion`-Bump, `onUpgrade` und `build_runner`. | Sonnet | `providers/share_intent_provider.dart`, `repositories/items_repository.dart`, `database/*` | B1 | Reihenfolge und Persistenz |
| B3 | WorkManager-OneOff-Job „flush-queue“ mit Constraint `networkType.connected`, exponentiellem Backoff und Notification „gespeichert“ bzw. „wartet auf Netz“. Der Job muss im Hintergrund-Isolate die Einstellungen (API-URL, Key) lesen. | Sonnet | `services/background_sync.dart` (neu) | B2 | Isolate-Zugriff auf drift und Prefs |
| B4 | Geteilter Text ohne URL wird als Notiz eingereiht (`ingestText`), statt verworfen zu werden. | Haiku | `share_intent_provider.dart:80-83` | B2 | Kleine Fallunterscheidung |
| B5 | Periodischer Sync (alle 3 h, nur bei Netz). Er synchronisiert Items und leert die Queue; die Watchlist-Poll-Funktion (D18) hängt sich später hier an. | Sonnet | `background_sync.dart` | B3 | Wiederverwendung |
| B6 | Gerätetest per adb auf dem Defy: Flugmodus an, Link teilen (die App beendet sich sofort), Flugmodus aus. Nach ≤ 1 min ist das Item im Backend (`/items`). Screenshot und uiautomator-Prüfung. | Haiku | Skript `scripts/test-share-offline.sh` | B3 | Mechanische adb-Schritte (Flugmodus per `cmd connectivity`, notfalls Stefan) |
| B7 | Release 0.7.x: Version und CHANGELOG. | Haiku | 3 Stellen, CHANGELOG | B6 | Mechanisch |

**Verifikation B:**
- B6 automatisiert. Zusätzlich: ein Share bei laufendem Fetch verliert nichts.
- `flutter analyze` ohne Infos.

---

## Phase C: Embedding-Wechsel, Eval-Harness, Chat-Modell

Die Reihenfolge ist zwingend: **zuerst der Modellfilter, dann der Wechsel**, sonst mischen sich alte und neue Vektoren. Die neue Dimension ist ebenfalls 1024; damit ist die alte Sperre aus `IMPLEMENTATION-PLAN.md` („mxbai NICHT anfassen“) aufgehoben, weil kein Schemawechsel nötig ist. C1/C2 und C5 sind parallelisierbar.

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| C1 | Filter `ContentEmbedding.model == settings.embedding_model` in RAG `_retrieve`, Triage, SIMILAR-Relations und Resurfacing. | Sonnet | `services/rag.py`, `triage.py`, `processing.py`, `resurface*` | — | Mehrere Queries konsistent anfassen |
| C2 | Query-Präfix je Modell (Map in `embeddings.py`): Für mxbai gilt „Represent this sentence for searching relevant passages: “, für qwen3-embedding „Instruct: Gegeben eine Frage, finde relevante Notizen\nQuery: “. Nur Queries bekommen einen Präfix, Dokumente nicht. Dazu ein Test. | Sonnet | `services/embeddings.py`, `rag.py:78-86` | — | Kleine Logik und Test |
| C3 | Prüfen, ob in `content_embeddings` ein Unique-Constraint `(content_id, model)` existiert. Falls nicht: additive Migration `010_embedding_model_unique`, damit alte und neue Vektoren nebeneinander liegen können. | Opus | `alembic/versions/010_*` | C1 | Constraint auf Bestandsdaten, die Ablösung muss sauber sein |
| C4 | Re-Embed-Job `python -m app.tools.reembed --model qwen3-embedding:0.6b`: fortsetzbar, in Batches, **schreibt neben** die alten Vektoren und schaltet nichts um. Fortschritt über `GET /admin/reprocess-status`. | Opus | `backend/app/tools/reembed.py` (neu) | C3 | Läuft lange auf Prod-Daten |
| C5 | Eval-Harness `backend/scripts/eval_models.py`, angewendet auf 20 echte Items aus einem Prod-Dump in der Dev-DB:<br>• Chat-Metriken: JSON-Validität, Anteil deutsch, Latenz p50/p95, Summary-Länge.<br>• Embedding-Metriken: Recall@5 auf Paaren (ähnlich bzw. unähnlich).<br>• Ausgabe als Markdown-Tabelle. | Sonnet | `backend/scripts/eval_models.py`, `backend/eval/` | — | Messwerkzeug |
| C6 | Eval-Datensatz: 20 Item-IDs und etwa 30 Paare. Vorschlag: automatisch aus Topic-Overlap und Ratings ableiten. Stefan bestätigt bzw. korrigiert die Paare in ~10 min. | Haiku, dann Stefan | `backend/eval/pairs.json` | C5 | Auswahl ist mechanisch, das Urteil fällt Stefan |
| C7 | **Schwellen-Kalibrierung:** Cosine-Verteilungen alt und neu auf den Paaren vergleichen. Neue Schwellen für SIMILAR (bisher 0,75), Triage und Near-Dup (für D11) so wählen, dass die Precision der Kantendichte beim alten Modell entspricht. Werte kommen in `config.py`, die Herleitung in `backend/eval/README.md`. | Opus | `config.py`, `backend/eval/` | C4, C6 | Statistische Kalibrierung |
| C8 | Umschalten: `EMBEDDING_MODEL` setzen, SIMILAR-Relations neu aufbauen (vorhandener Admin-Endpunkt bzw. das Skript). Alte Vektoren erst nach einer Woche per `--purge-model` löschen. | Sonnet | `tools/reembed.py`, `.env`-Doku | C7 | Umschalt- und Rollback-Pfad |
| C9 | Chat-Modell-Eval: `qwen2.5:3b` (Ist), `qwen3:4b-instruct-2507-q4_K_M` und `granite4.2:3b` mit C5 vergleichen. Die VPS-Grenzen werden auf dem Dev-Rechner emuliert (Ollama-Container mit `--cpus=4 --memory=6g`, `num_ctx` 8192). Ergebnis als Tabelle. | Sonnet | Dev, `backend/eval/results-*.md` | C5, A3.1 | Messung und Bewertung |
| C10 | VPS-Kommandoblock: Modelle pullen, `.env` setzen, `docker compose up -d` (**nicht** `restart`). Danach `/admin/ollama/check`. | Haiku | `DEV.md` bzw. Ops-Notiz | C8, C9 | Abschreiben |
| C11 | VPS-Umschaltung (Embedding und gegebenenfalls Chat) mit vorherigem Backup. | **Stefan (SSH)** | VPS | C10 | Nur per SSH möglich |
| C12 | Doku nachziehen: `CLAUDE.md` Prod-Setup (Modelle, Schwellen), Hinweis zum `IMPLEMENTATION-PLAN.md`-Constraint. | Haiku | `CLAUDE.md`, `IMPLEMENTATION-PLAN.md` | C11 | Fakten nachtragen |

**Verifikation C:**
- Recall@5 neu ≥ alt; sonst kein Wechsel.
- RAG-Chat liefert für 5 Testfragen Quellen.
- Nach C11 zeigt `/admin/ollama/check` beide Modelle verfügbar; ein Prod-Ingest erzeugt ein Embedding mit dem neuen `model`.

---

## Phase D: Watchlist („Radar“)

Voraussetzungen: A1 (Hash), A2 (Fetcher), A4 (asynchroner Pfad, Queue). Für das Relevanz-Gate C7 (Schwellen) ist das empfohlen; mit den alten Schwellen geht es vorläufig auch.
Migrationsnummer: **011** (009 und 010 sind durch A4.1 und C3 belegt; im Bericht hieß sie noch „009“).
Parallelisierbar sind nach D3: Backend (D4–D13) und App (D15–D17, gegen eine gemockte API).

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| D1 | **Design** `WATCHLIST.md` auf Basis des Berichts §3:<br>• Datenmodell, Quell-Typen für das MVP (rss, youtube), Status-Automat der Entries, Initial-Seeding.<br>• Zwei Queues mit Priorität (manuell vor watch), Tageslimit `watch_max_llm_per_day`.<br>• Notification-Strategie, Abgrenzung zum Weekly. | Fable | `WATCHLIST.md` (neu) | A4 | Konzeptweiche, alles Weitere hängt daran |
| D2 | Migration **`011_watch_sources`**: `watch_sources` und `watch_entries` (inkl. Enums `kind`/`status`), `content_items.origin` (Default `manual` für Bestandsdaten) und `watch_source_id` (FK `SET NULL`). | Opus | `alembic/versions/011_*` | D1 | Enums, FKs, Backfill auf Prod-Daten |
| D3 | SQLAlchemy-Models und Pydantic-Schemas exakt nach D2. | Haiku | `models/watch.py`, `schemas.py` | D2 | Abschreiben aus Migration und Design |
| D4 | Tick-Scheduler:<br>• alle 5 min `SELECT … enabled AND next_poll_at<=now ORDER BY next_poll_at LIMIT 5 FOR UPDATE SKIP LOCKED`;<br>• Backoff `interval·2^failures` (max. 24 h), ab 10 Fehlern `enabled=false`;<br>• `Retry-After` beachten. | Sonnet | `services/watch/scheduler.py`, Hook in `services/scheduler.py` | D3 | Scheduler-Logik |
| D5 | Prioritäts-Queue im Processing: Manuelle Items schlagen Watch-Items (zwei Semaphoren oder eine `PriorityQueue`). Dazu der Zähler fürs Tageslimit. | Sonnet | `services/processing.py` | D3, A4.4 | Nebenläufigkeit, überschaubar |
| D6 | RSS/Atom-Adapter (`feedparser`) über `safe_fetch` mit ETag/Last-Modified; Feed-Content-Types in die Allowlist. **Initial-Seeding:** Beim ersten Abruf werden alle Einträge `seen`. | Sonnet | `services/watch/rss.py`, `fetcher.py` | D4, A2.2 | Adapter mit Zustand |
| D7 | Autodiscovery beim Anlegen einer Quelle: `<link rel=alternate type=application/rss+xml>` suchen. | Haiku | `services/watch/discover.py` | D6 | Einfacher HTML-Parse nach Muster |
| D8 | YouTube: `@handle` bzw. Kanal-URL zu `channel_id` auflösen (ein HTML-Fetch), dann `feeds/videos.xml?channel_id=` über den RSS-Adapter. | Sonnet | `services/watch/youtube.py` | D6 | Parsing mit Randfällen |
| D9 | YouTube-Inhalt: `youtube-transcript-api`, Fallback Beschreibung plus Titel. Läuft der Transkript-Abruf über den Homeserver, ist das eine Entscheidung (siehe unten). | Sonnet | `youtube.py`, `extractor.py` | D8 | Fallback-Kette |
| D10 | **Relevanz-Gate-Konzept:**<br>• Score-Formel (max. Cosine zu hoch bewerteten Items plus Interessen-Zentroid über 90 Tage, gewichtet nach Rating);<br>• negatives Feedback aus „verwerfen“;<br>• Default für `min_relevance`, Near-Dup bei Cosine > Schwelle aus C7;<br>• Kaltstart-Verhalten. | Fable | Abschnitt in `WATCHLIST.md` | D1 | Strategieweiche, bestimmt die LLM-Kosten |
| D11 | Relevanz-Gate implementieren: Titel und Snippet einbetten, Score berechnen (Wiederverwendung `triage.py:_score_for_embedding`), Zentroid cachen. Bei Score ≥ Schwelle `auto_ingest` über den A4-Pfad, sonst `status=new`. | Opus | `services/watch/relevance.py` | D10, D5 | Algorithmus und Kalibrierung |
| D12 | API-Router `/watch`:<br>• Quellen: CRUD, `POST …/test` (Probeabruf);<br>• Entries: `GET /watch/entries?since=&status=`, `POST /watch/entries/{id}/accept\|dismiss`.<br>Die festen Pfade stehen **vor** den int-Pfadparametern. | Sonnet | `routers/watch.py`, `main.py` | D3 | Standard-API |
| D13 | Tests:<br>• Scheduler (SKIP LOCKED, Backoff, Disable);<br>• RSS mit Fixture-Feed (Seeding, keine Doppel-Entries);<br>• Relevanz-Gate mit Fake-Embeddings;<br>• API-Roundtrip. | Sonnet | `tests/test_watch_*.py` | D4–D12 | Neue Testszenarien |
| D14 | Adapter-Tests für Discovery und YouTube-Handle mit HTML-Fixtures. | Haiku | `tests/fixtures/`, `tests/test_watch_discover.py` | D7, D8 | Vorlage aus D13 |
| D15 | App-Datenschicht: Watch-API im Client, Modelle, Riverpod-Provider. | Sonnet | `app/lib/…` | D12 (oder Mock) | Standard |
| D16 | App: Tab „Radar“ mit Quellenliste. Quelle per URL hinzufügen, Toggles für auto und notify, Fehlerstatus anzeigen. | Sonnet | `app/lib/screens/radar/*`, `go_router` | D15 | UI |
| D17 | App: Entry-Liste nach Relevanz, Swipe für „übernehmen“ bzw. „verwerfen“ (`flutter_slidable` ist schon vorhanden). | Sonnet | `screens/radar/entries.dart` | D16 | UI |
| D18 | Notifications: Channel „Überwachung“ und eine Sammel-Notification pro Poll. Der Poll hängt am periodischen WorkManager-Job aus B5. | Sonnet | `notification_service.dart`, `background_sync.dart` | B5, D15 | Hintergrund-Integration |
| D19 | Weekly-Digest bekommt eine eigene Sektion für Watch-Items (`origin=watch`). Der Prompt-Abschnitt kommt per Haiku-Teil. | Sonnet | `routers/weekly.py`, Prompt | D2, A3.5 | Kleine Integration |
| D20 | Optional: Adapter für Reddit, Mastodon und HN (Algolia `points>N`), nach dem RSS-Muster. | Haiku | `services/watch/*.py` | D6 | Variation einer Vorlage |
| D21 | Optional, später: Seiten-Diff (`page`) und `sitemap`. | Sonnet | `services/watch/page.py` | D6 | Diff-Logik |
| D22 | Doku (`WATCHLIST.md` Ist-Stand, `CLAUDE.md`), Version und CHANGELOG (0.8.0). | Haiku | Doku, 3 Versionsstellen | D19 | Mechanisch |

**Verifikation D:**
- `./dev.sh test` grün.
- Dev mit 3 echten Feeds (1 RSS, 1 YouTube, 1 tote URL):
  - Das Seeding meldet nichts.
  - Ein neuer Eintrag erscheint im Radar.
  - Die tote URL wird nach Fehlern zurückgestellt (Backoff).
  - Das Tageslimit greift (Test mit Limit 1).
- App auf dem Defy: Radar-Tab, Swipe und Notification per adb/uiautomator prüfen.

---

## Phase E: Capture-Kanäle (unabhängig, ab Phase A parallel möglich)

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| E1 | Browser-Extension MV3 (Firefox und Chrome, ein Code): Toolbar-Button speichert den Tab, Kontextmenü speichert die Markierung als Notiz. Optionsseite für API-URL und Key (`storage.local`). | Sonnet | `extension/` (neu, ca. 100 Zeilen) | A4.4 | Manifest, Permissions, zwei Browser |
| E2 | Bookmarklet als Fallback mit Doku. Es öffnet `…/share?url=` als kleine Form-Seite, statt den Key in den Bookmark zu legen; CORS bleibt dicht. | Haiku | `extension/bookmarklet.md`, minimaler Endpunkt nur falls nötig | E1 | Nach Vorlage |
| E3 | Telegram-Bot per Long-Polling als Task im API-Prozess, Whitelist `TELEGRAM_CHAT_ID`. URL ergibt Ingest, Text ergibt Notiz. Token in `.env`. | Sonnet | `services/telegram.py`, `config.py` | A4.4 | Integration |
| E4 | Telegram-Rückmeldung: Bei `COMPLETED` geht eine TL;DR plus Link an den Chat (Hook in `processing.py`). Optional später Watch-Sammelmeldungen. | Sonnet | `telegram.py`, `processing.py` | E3 | Ereignis-Hook |
| E5 | Tests für Telegram mit gemocktem Bot-API (Whitelist, URL vs. Text). | Haiku | `tests/test_telegram.py` | E4 | Vorlage aus E3 |
| E6 | IMAP-Poll auf ein eigenes Postfach (`IMAP_*` in `.env`, alle 15 min). Mails werden zu `ContentType.NEWSLETTER` (Text aus HTML per trafilatura) und danach als gelesen markiert bzw. verschoben. | Sonnet | `services/imap_ingest.py` | A4.4 | Integration |
| E7 | IMAP-Tests mit einer Fixture-Mail und Doku in `DEV.md`. | Haiku | `tests/test_imap.py`, `DEV.md` | E6 | Vorlage |

**Verifikation E:**
- Die Extension in Firefox **und** Chrome gegen die Dev-API testen (Playwright oder manuell per Claude-in-Chrome); ein Item entsteht.
- Telegram mit einem Test-Bot: Nachricht senden ergibt ein Item und eine TL;DR-Antwort.
- IMAP gegen ein Test-Postfach (Credentials von Stefan, Eintrag als TODO).

---

## Phase F: Export, Performance, Ops-Kleinkram, Testlücken

Fast alle Punkte sind **untereinander unabhängig** und eignen sich als Lückenfüller zwischen größeren Blöcken. F8 bis F12 sollten vor Phase D erledigt sein (Prompt-Injection).

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| F1 | Obsidian-Export: YAML-Frontmatter (`url`, `tags`, `rating`, `created`, `source`), sauber escaped (`yaml.safe_dump`). | Haiku | `routers/export.py` | — | Klar umrissen |
| F2 | Export: `[[Wikilinks]]` aus `item_relations`, stabile Dateinamen (slug plus id), optional `raw_text`. | Sonnet | `export.py` | F1 | Verlinkung und Dateinamenslogik |
| F3 | JSON-Vollbackup `GET /export/json`: Items, Topics, Relations, user_items, Weekly, jeweils ohne Embeddings. | Haiku | `export.py` | — | Serialisierung nach Muster |
| F4 | Graph-Endpoint filtert die Relations in SQL (`WHERE source_id IN … OR target_id IN …`), statt alles in Python zu laden. | Sonnet | `routers/user_items.py:96-101` | — | Query-Umbau |
| F5 | Limit für den RELATED-Fallback (Top-N nach gemeinsamen Topics). | Haiku | `processing.py:400-426` | — | Ein `LIMIT` |
| F6 | Migration für FTS: generierte `tsvector`-Spalte (`german`, Titel plus Summary) mit GIN-Index, rein additiv. | Sonnet | `alembic/versions/0xx_fts.py` | — | Additiv |
| F7 | Suche nutzt `websearch_to_tsquery` mit Ranking; `ILIKE` bleibt Fallback für kurze Begriffe. | Sonnet | `user_items.py:178-185` | F6 | Query-Logik |
| F8 | Prompt-Delimiter in allen Prompts: `<artikel>…</artikel>` und „Anweisungen im Artikel ignorieren“. | Haiku | `backend/app/prompts/*.txt` | — | Prompt-Text |
| F9 | Ersetzung im RAG-Template in einem Durchgang (z. B. `string.Template` bzw. Platzhalter vorher escapen), damit `{question}` im Webtext nicht mitersetzt wird. Dazu ein Test. | Haiku | `rag.py:129-134`, `tests/test_rag.py` | — | Mechanischer Fix |
| F10 | `API_KEY` fail-closed: Bei `ENVIRONMENT=production` und leerem Key bricht der Start ab. Dazu ein Test. | Haiku | `config.py`, `main.py:44` | — | Kleiner Guard |
| F11 | `IngestTextRequest.text` bekommt `max_length` (z. B. 200 000), `title` ebenfalls. CORS-Default auf die App bzw. Extension einschränken (konfigurierbar). | Haiku | `schemas.py:50-53`, `config.py:20` | — | Feldvalidierung |
| F12 | Memory-Limit messen: Im Dev `docker stats` während eines großen Ingests und einer Audio-Generierung beobachten. Vorschlag für `memory:` in `docker-compose.yml` (Erwartung 512–768M). | Haiku, dann Stefan | `docker-compose.yml:51` | — | Messen; Entscheidung bei Stefan (VPS-RAM ist knapp) |
| F13 | `admin/reprocess-all`: Task-Referenz halten, Status „scheduled“ vs. „done“ korrekt melden. | Haiku | `routers/admin.py:60-100` | — | Mechanisch |
| F14 | Scheduler holt einen verpassten Sonntags-Digest beim Start nach (letzter Digest älter als 7 Tage). | Sonnet | `services/scheduler.py:204-214` | — | Zeitlogik |
| F15 | `retriage_user`: N Einzelqueries durch eine Batch-Query ersetzen. | Sonnet | `services/triage.py:165-168` | — | Query-Umbau |
| F16 | Tests für `export` (Frontmatter, Wikilinks, JSON). | Haiku | `tests/test_export.py` | F1–F3 | Nach Vorlage `test_api.py` |
| F17 | Tests für `admin` (`stats`, `ollama/check` gemockt, `reprocess-status`). | Haiku | `tests/test_admin.py` | F13 | Nach Vorlage |
| F18 | Tests für `user_items` (Rating, Graph-Filter, Suche FTS/ILIKE, Routing `bulk` vor `{id}`). | Sonnet | `tests/test_user_items.py` | F4, F7 | FTS braucht die Test-DB-Migration |
| F19 | Release 0.7.x/0.8.x: Version und CHANGELOG. | Haiku | 3 Stellen | — | Mechanisch |

**Verifikation F:**
- `./dev.sh test` grün.
- Obsidian-Export in einen leeren Vault importiert: Links funktionieren, das Frontmatter wird erkannt.
- Suche nach einem deutschen Flexionswort findet die Grundform.
- Ein Start mit `ENVIRONMENT=production` ohne Key bricht ab.

---

## Phase G: Doku-Drift

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| G1 | `TODO.md` mit dem Ist-Stand abgleichen: RAG-Chat, Resurfacing, Triage und Audio-Digest sind **bereits gebaut** (v0.6.x). Offene Punkte auf diesen Plan verweisen. | Haiku | `TODO.md` | — | Doku |
| G2 | `CLAUDE.md`, Abschnitt „Offene Ideen“: Gebautes streichen, auf `PLAN-v0.7.md` verweisen. Neue Architekturentscheidungen nach ihrer Umsetzung eintragen (Fetcher, asynchroner Ingest, Rehash-CLI, Embedding-Modell). | Haiku | `CLAUDE.md` | jeweils nach A/C/D | Doku |
| G3 | `IMPLEMENTATION-PLAN.md`: Vermerk, dass das Embedding-Constraint durch Phase C ersetzt ist. | Haiku | `IMPLEMENTATION-PLAN.md` | C11 | Doku |

---

## Phase H (optional): APK-Diät, statt nach Kotlin zu portieren

**Messung (2026-10-14, nur gelesen):**
- APK-Größen im Repo-Root: v0.2.0 hatte **50,95 MB**, v0.3.3 **51,8 MB**, v0.3.8 **59,7 MB**. Neuere APKs liegen nicht im Root.
- `unzip -l v0.3.8`: Es ist eine **Fat-APK mit 3 ABIs**. Pro ABI liegen bei:
  - `libflutter.so` mit 8,1 MB (v7a), 11,1 MB (arm64) bzw. 12,3 MB (x86_64);
  - `libapp.so` (Dart-AOT) mit 7,0–7,8 MB;
  - `libsqlite3.so` mit 1,5 MB.

  Dazu kommt 1,9 MB Dex.

  **Nur arm64** wären etwa **21 MB, also −63 %**. Für das Defy reicht arm64 [A: SoC ist arm64].
- `android/app/build.gradle.kts` hat **R8 (`isMinifyEnabled`) und `isShrinkResources` bereits aktiv**. CI (`flutter-release.yml:67,71`) baut ein AppBundle und eine Fat-APK, aber **ohne `--split-per-abi`**.
- Abhängigkeiten (`pubspec.yaml`) sind schlank. Native Größe bringen nur `sqlite3_flutter_libs` (1,5 MB pro ABI) und `just_audio` (ExoPlayer im Dex). `shimmer`, `graphview` und `cupertino_icons` sind klein.
- Die App hat etwa **7 800 Zeilen Dart** (ohne `*.g.dart`).

**Bewertung:**

| Option | Ersparnis | Aufwand | Risiko |
|---|---|---|---|
| `flutter build apk --split-per-abi` (nur arm64 sideloaden) | ~60 MB auf ~21 MB | 15 min | keines |
| `--obfuscate --split-debug-info` | `libapp.so` −10–20 % [A] | 15 min | Stacktraces brauchen die Symboldatei |
| App-Bundle (Play liefert pro ABI und Dichte) | Download etwa wie Split | ist schon gebaut | nur relevant mit Play-Store |
| R8 und Resource-Shrinking | — | ist schon aktiv | — |
| Abhängigkeiten reduzieren (`cupertino_icons`, `shimmer`) | < 0,5 MB | 30 min | gering |
| **Kotlin/Compose-Rewrite** | auf ~6–10 MB [A], Kaltstart etwa 100–300 ms schneller [A] | **~3–5 Wochen**: 7 800 Zeilen UI, drift → Room samt Migration der lokalen DB, Riverpod → ViewModel/Flow, Audio, Graph-View, Share und WorkManager neu | Feature-Stillstand, keine iOS-Option mehr, zwei Codebasen während der Portierung |

**Empfehlung:** **Kein Kotlin-Rewrite.**
- Der Größenunterschied schrumpft durch den ABI-Split von etwa 50 MB auf etwa 12–15 MB.
- Bei einer Single-User-Sideload-App kostet das Speicher, aber keine Nutzer.
- Die Laufzeit-Performance ist bei Flutter-AOT für Listen und Formulare kein Engpass.
- Die Engpässe liegen im Backend: LLM-Latenz auf dem VPS.
- Phase H kostet etwa 1–2 h.

Neu bewerten nur, wenn ein Kaltstart-Messwert über 1,5 s liegt (H4) oder echte native Features (z. B. Widgets oder Tiles) unverhältnismäßig schwer werden.

| # | Aufgabe | Modell | Scope/Dateien | Abh. | Begründung |
|---|---|---|---|---|---|
| H1 | Messen: `flutter build apk --release --split-per-abi` und `--analyze-size --target-platform android-arm64`, Größen pro ABI tabellieren (aktueller Stand v0.6.5). | Haiku | lokal, Ergebnis in `DEV.md` | — | Kommandos und Tabelle |
| H2 | CI: `flutter-release.yml` baut `--split-per-abi --obfuscate --split-debug-info=build/symbols`, lädt die arm64-APK als Haupt-Asset hoch und die Symbole als Artifact. | Haiku | `.github/workflows/flutter-release.yml` | H1 | Mechanisch |
| H3 | Kaltstart auf dem Defy messen (`adb shell am start -W`, 5 Läufe, Median) und Speicher (`dumpsys meminfo`). | Haiku | Skript bzw. `DEV.md` | H1 | adb-Routine |
| H4 | Abhängigkeits-Check: ungenutzte Pakete entfernen (`cupertino_icons` prüfen), `flutter analyze` sauber. | Haiku | `pubspec.yaml` | H1 | Mechanisch |

---

## Reihenfolge und Parallelität

1. **Phase A.** A1 ∥ A2 ∥ A3 ∥ (A4.1, A4.2). Danach A4.3 bis A4.9. Parallel dazu: G1, F8–F11, H1/H2 (alles Haiku, konfliktfrei).
2. **B ∥ C.** Phase B ist reine App-Arbeit, Phase C reine Backend- und Eval-Arbeit, sie kommen sich nicht in die Quere. E1–E3 können parallel laufen.
3. **Phase D**, nach A, B5 und F8/F9; besser auch nach C7. Innerhalb von D laufen Backend und App ab D3 parallel.
4. Danach der Rest von **E und F**, **G2/G3** jeweils nach den Meilensteinen.

Nutzen pro Aufwand, höchster zuerst: A1, A3.1, A4, A2, B, F8–F11, C, H, D, E, F-Rest.

## Offene Entscheidungen (Stefan, gebündelt)

1. **Rehash in Prod (A1.4):** CLI statt automatischer Migration, Ausführung erst nach Backup und Dry-Run-Bericht. Kollisionen bekommen ein Suffix und werden nicht gelöscht. **Empfehlung: ja.**
2. **Ingest-Antwort 202 statt 200 mit fertigem Item (A4.4):** Die App sieht das Item sofort als `PENDING`. Ältere App-Versionen müssen zuerst aktualisiert werden. **Empfehlung: ja**, App und Backend im selben Release ausliefern.
3. **Embedding-Wechsel auf `qwen3-embedding:0.6b` (C8/C11):** nur wenn Recall@5 neu ≥ alt. **Empfehlung: ja**, mit einer Woche Parallelbetrieb.
4. **Chat-Modell (C9):** **Empfehlung:** `qwen3:4b-instruct-2507-q4_K_M`, wenn JSON-Validität ≥ 98 % und p95 ≤ 1,5 × Ist bei ≤ 6 GB RAM gelingen; sonst `qwen2.5:3b` behalten.
5. **YouTube-Transkripte (D9):** VPS-IPs werden oft geblockt. **Empfehlung:** MVP nur mit Beschreibung und Titel; der Transkript-Abruf über den Homeserver kommt später als eigener Punkt.
6. **Telegram-Bot im API-Prozess vs. eigener Container (E3):** **Empfehlung: im API-Prozess** (ein Worker, kein Mehrbedarf an RAM auf dem VPS).
7. **Memory-Limit (F12):** **Empfehlung:** 768M, falls die Messung über 200M Peak liegt; der VPS-RAM bleibt der Engpass.
8. **Kotlin-Rewrite:** **Empfehlung: nein**, stattdessen Phase H (ca. 1–2 h).
9. **Eval-Paare (C6):** Stefan bestätigt etwa 30 automatisch vorgeschlagene Paare (ca. 10 min).

## Modell-Zählung und Kostenschätzung

| Modell | Anzahl | Aufgaben |
|---|---|---|
| Haiku 4.5 | **40** | A1.2, A1.5, A2.4, A3.1, A3.4, A4.6, A4.9 · B4, B6, B7 · C6, C10, C12 · D3, D7, D14, D20, D22 · E2, E5, E7 · F1, F3, F5, F8–F13, F16, F17, F19 · G1–G3 · H1–H4 |
| Sonnet 5.5 | **47** | A1.1, A2.2, A2.3, A3.2, A3.3, A3.5, A3.6, A4.1–A4.5, A4.7, A4.8 · B1, B2, B3, B5 · C1, C2, C5, C8, C9 · D4–D6, D8, D9, D12, D13, D15–D19, D21 · E1, E3, E4, E6 · F2, F4, F6, F7, F14, F15, F18 |
| Opus 5.5 | **9** | A1.3, A1.4, A2.1, A2.5, C3, C4, C7, D2, D11 |
| Fable 5.1 | **2** | D1, D10 |
| Stefan (SSH/Urteil) | 3 Anteile | C6 (Paare), C11 (VPS), F12 (Limit-Freigabe) und die gebündelten Entscheidungen |

**Relative Token-Kosten:**
- Angenommene Gewichte pro Aufgabe: Haiku = 1, Sonnet ≈ 4, Opus ≈ 12, Fable ≈ 20. Darin steckt Preis × typischer Kontext- und Denkbedarf [A].
- Rechnung: 40·1 + 47·4 + 9·12 + 2·20 = 40 + 188 + 108 + 40 = **≈ 376 Einheiten** (98 Aufgaben).
- Zum Vergleich: alles mit Sonnet wäre 98·4 ≈ 392, alles mit Opus 98·12 ≈ 1176.
- Ersparnis gegenüber „alles Opus“ etwa 68 %.
- Den Kostenhebel liefern die 9 Opus- und 2 Fable-Aufgaben (zusammen ≈ 39 %). Sie stecken genau in Security, Prod-Daten-Migrationen, Kalibrierung und den zwei Designweichen.
- Für Haiku sind bewusst Doku, Tests nach Vorlage, mechanische Fixes und adb/CI vorgesehen.

---

*Erstellt 2026-10-14 per Modell-Vorauswahl. Etiketten bei Bedarf während der Ausführung nachziehen.*
