# Implementierungsplan: Doku-Drift, Ollama, Deutsch-Bug, Modellwechsel (2026-07-19)

Dieser Plan bündelt die offenen Punkte aus der Umgebungs-Erhebung vom 2026-07-19
(Faktenblatt + Modell-Recherche der Session) zu ausführungsreifen Aufgaben.

**Methode: Modell-Vorauswahl.** Jede Aufgabe trägt ein Modell-Etikett — das
*schwächste noch ausreichende* Modell, einmalig strategisch festgelegt (Fable).
Die Ausführung liest das Etikett nur ab, statt bei jedem Schritt neu über die
Modellwahl nachzudenken: einmal teuer denken, oft billig ausführen. Die
Vorauswahl ist Vorschlag, kein Dogma — zeigt sich eine Aufgabe schwerer,
hochstufen und das Etikett hier nachziehen.

| Modell | Wofür |
|---|---|
| **Haiku 4.5** | Klare, repetitive Arbeit: Doku-Edits, Prompt-Text, Boilerplate, mechanische Fixes |
| **Sonnet 5** | Standard-Entwicklung: Code mit Logik, Integration, Test-Gerüste, Docker/Compose |
| **Opus 4.8** | Algorithmen, kniffliges Denken, heikle Migrationen |
| **Fable 5** | Strategie/Design/Konzept-Weichen (dieser Plan selbst) |
| **? Nachfragen** | Scope/Entscheidung offen — erst Stefan fragen bzw. messen, dann ausführen |

Grundlagen (nicht im Repo, Session-Scratchpad): `env-factsheet.md`,
`model-research.md`. Harte Constraints daraus: Embedding-Modell bleibt
**`mxbai-embed-large`** (pgvector-Spalte `vector(1024)` — NICHT anfassen);
flexibel ist nur das Chat-Modell `OLLAMA_MODEL`.

---

## Phase 1 — Doku-Drift & Docker (pop-os)

Die Doku hinkt der Realität hinterher: pop-os hat inzwischen Docker 29.6.1 +
Compose v5.3.1, Ollama läuft dort als Container (`ollama/ollama:latest`,
v0.13.5, API `:11434`, CLI nur via `docker exec ollama ollama ...`), der
Dev-Stack (`./dev.sh up`) ist auf pop-os End-to-End verifiziert, und Flutter
3.38.5 liegt unter `~/flutter/bin` (nur in nicht-interaktiven Shells nicht im
PATH). Erst Doku fixen, dann bauen — sonst arbeitet jede Folge-Session mit
falschen Annahmen.

| # | Aufgabe | Modell | Scope/Dateien | Abhängigkeit | Begründung |
|---|---|---|---|---|---|
| 1.1 | Fix outdated CLAUDE.md pitfall "lokal kein Docker/Postgres" | Haiku | `CLAUDE.md` (Stolperfallen + Dev-Umgebung): pop-os ist vollwertiger zweiter Dev-Standort (Docker/Compose vorhanden, `./dev.sh` läuft, Backend-Tests lokal möglich) | — | Faktischer Doku-Edit, Inhalt steht im Faktenblatt |
| 1.2 | Flutter clarification (present, PATH note) | Haiku | `MIGRATION.md` (Abschnitt "Offen geblieben": "Flutter fehlt" präzisieren — gilt nur für den Homeserver; pop-os hat 3.38.5 unter `~/flutter/bin`), `DEV.md` (PATH-Hinweis: nicht-interaktive Shells brauchen `export PATH="$HOME/flutter/bin:$PATH"`) | — | Klartext-Korrektur nach Faktenlage |
| 1.3 | DEV.md: pop-os section (Docker-Ollama specifics) | Haiku | `DEV.md`: kurzer Abschnitt "Dev auf pop-os" — gleiche Ports (:8100/:5433), Ollama containerisiert → Modelle via `docker exec ollama ollama pull ...` oder HTTP-API, `OLLAMA_BASE_URL=http://host.docker.internal:11434` gilt auch hier | 1.1 | Struktur ist hier vorentschieden (DEV.md bleibt homeserver-zentriert, pop-os als Zusatzabschnitt); Edit selbst ist mechanisch |
| 1.4 | Docker housekeeping: inventory only | Haiku | pop-os: `docker images`, `docker ps -a`, `docker system df` → Kandidatenliste alter Images/Container/Volumes als Textliste an Stefan | — | Reines Auflisten; NICHTS löschen |
| 1.5 | Docker housekeeping: prune | **?** | Löschen nur nach Stefans Bestätigung der Liste aus 1.4 (dann Haiku: `docker rm/rmi` gezielt, kein pauschales `system prune -a`) | 1.4 | Löschen fremder Container/Volumes ist irreversibel — Entscheidung gehört Stefan |

**Verifikation Phase 1:** Doku-Diff gegenlesen (kein Widerspruch mehr zwischen
CLAUDE.md/DEV.md/MIGRATION.md und Faktenblatt); Flutter-PATH-Hinweis real
testen: `bash -c 'export PATH="$HOME/flutter/bin:$PATH"; flutter --version'`
in nicht-interaktiver Shell liefert 3.38.5. Nach 1.5: `docker ps` — dev-Stack
und Ollama-Container laufen unverändert.

---

## Phase 2 — Ollama-Update (pop-os)

Ollama v0.13.5 im Container aktualisieren. Der Container ist NICHT Teil
unserer Compose-Dateien (eigenständig angelegt) — vor dem Recreate erst
`docker inspect` auf Volumes/Ports/Restart-Policy, damit nichts verloren geht
(Modelle liegen im Volume und überleben das Recreate).

| # | Aufgabe | Modell | Scope/Dateien | Abhängigkeit | Begründung |
|---|---|---|---|---|---|
| 2.1 | Update Ollama container (pull + recreate) | Sonnet | pop-os: `docker inspect ollama` (Volume/Port/Restart-Policy sichern) → `docker pull ollama/ollama:latest` → Container mit identischer Konfiguration neu erstellen | — | Kein Muster-Rezept: Container-Konfig muss erst gelesen und exakt reproduziert werden — echte Integrationssorgfalt |
| 2.2 | Document Ollama update procedure | Haiku | `DEV.md` (pop-os-Abschnitt aus 1.3): die in 2.1 verifizierte Prozedur als 3-Zeilen-Rezept | 1.3, 2.1 | Abschreiben der erprobten Schritte |

**Verifikation Phase 2:** `docker exec ollama ollama -v` zeigt Version >
0.13.5; `docker exec ollama ollama list` zeigt die vorherigen Modelle
(inkl. `mxbai-embed-large`, `qwen2.5:7b`, `qwen3:4b-instruct`) weiterhin;
`curl -s localhost:11434/api/version` antwortet; danach ein Ingest-Roundtrip
über den Dev-Stack (`:8100`) — Summary + Topics + Embedding entstehen wie
zuvor (Vergleich: Test-Item #2 der Erhebungs-Session).

---

## Phase 3 — Deutsch-Summary-Bug

Root-Cause (Session-verifiziert): `backend/app/prompts/summary.txt` ist
komplett englisch und sagt nur "Respond in the same language as the input
text" → Summaries kommen englisch trotz deutschem Input. `topics.txt` und
`weekly_summary.txt` sind bereits deutsch. JSON-Validität ist bei Ollama
grammar-constrained garantiert — die Sprache ist ein reines Prompt-Thema
(Summary läuft ohnehin ohne Schema, als Freitext). Entscheid (siehe "?"-Block,
Empfehlung: bestätigen): Summaries **immer Deutsch**, auch bei englischen
Quellen.

| # | Aufgabe | Modell | Scope/Dateien | Abhängigkeit | Begründung |
|---|---|---|---|---|---|
| 3.1 | Rewrite summary prompt in German, force German output | Haiku | `backend/app/prompts/summary.txt`: Prompt komplett auf Deutsch, explizit "Antworte ausschließlich auf Deutsch", Struktur (5–7 Bulletpoints + Takeaways) beibehalten; `{text}`-Platzhalter unangetastet | — | Reiner Prompt-Text nach klarer Vorgabe, keine Codeänderung |
| 3.2 | Verify: German + English ingest → both summaries German | Haiku | Dev-Stack: je ein deutsches und ein englisches Test-Item per API ingesten, Summary-Sprache prüfen (mit `qwen2.5:7b`, dem aktuellen Dev-Modell) | 3.1 | Mechanischer curl-Roundtrip mit eindeutigem Prüfkriterium |
| 3.3 | Fallback: prompt tuning if small models drift to English | Sonnet | Nur falls 3.2 oder 4.3 scheitert: Prompt iterieren (z. B. deutsche Beispiel-Bullets als Few-Shot, Sprach-Anweisung ans Ende), erneut gegen beide Modelle testen | 3.2, 4.3 | Iteratives Prompt-Verhalten kleiner Modelle einschätzen = echte Logik |
| 3.4 | CHANGELOG entry + patch version bump | Haiku | `CHANGELOG.md`; Version synchron in `app/pubspec.yaml`, `backend/pyproject.toml`, `APP_VERSION` in `backend/app/main.py` (Projektregel "eine Version für App+Backend") | 3.2 | Mechanisch nach dokumentierter Versions-Regel |

**Verifikation Phase 3:** 3.2 ist die Verifikation (deutsches UND englisches
Item → beide Summaries deutsch, Topics weiterhin deutsch normalisiert).
Zusätzlich `./dev.sh test` grün (kein Test darf am Prompt-Text hängen).

---

## Phase 4 — Modellwechsel (Dev-Parität, dann VPS)

Recherche-Ergebnis: primär **`qwen3:4b-instruct`** (Non-Thinking-Tag! nicht
`qwen3:4b`), Fallback **`qwen2.5:3b`** (läuft nachweislich auf dem VPS). Der
finale VPS-Entscheid hängt an RAM/CPU des VPS — unbekannt, daher "?"-Gate.
Dev zuerst: `qwen3:4b-instruct` ist auf pop-os **bereits gepullt** → der neue
deutsche Prompt lässt sich vor jedem VPS-Schritt gegen das VPS-Kandidatenmodell
testen (Prompt-Parität), ohne irgendetwas zu installieren.

| # | Aufgabe | Modell | Scope/Dateien | Abhängigkeit | Begründung |
|---|---|---|---|---|---|
| 4.1 | Measure VPS resources (`free -h`, `nproc`, laufende Nachbardienste) | **? — NUR Stefan (SSH auf VPS)** | VPS-Shell; Ergebnis in den "?"-Block unten eintragen | — | Ohne RAM-Zahl keine seriöse Modellwahl (Recherche §5) |
| 4.2 | Decide VPS model per RAM class | Haiku | Entscheidungsregel aus `model-research.md` §2 anwenden: <~8 GB frei → `qwen2.5:3b`; ~8 GB → `qwen3:4b-instruct`; ≥16 GB → `qwen2.5:7b`/`qwen3:8b` | 4.1 | Regel steht fest, Anwendung ist Tabellen-Lookup |
| 4.3 | Dev parity test: new prompt vs. `qwen3:4b-instruct` | Sonnet | Dev-Stack pop-os: `OLLAMA_MODEL=qwen3:4b-instruct` in `backend/.env`, `./dev.sh up`, Test-Items aus 3.2 wiederholen; Sprache + Topic-Qualität + grobe Latenz notieren; danach `backend/.env` zurück auf `qwen2.5:7b` | 3.2 | Modellverhalten vergleichen und bewerten, nicht nur Kommandos abspulen |
| 4.4 | Prepare VPS switch command block | Haiku | Fertiger Kommandoblock für Stefan bzw. begleitete Session: auf VPS `docker compose exec ollama ollama pull <modell>` (bzw. Auto-Pull durchs Backend), `OLLAMA_MODEL=<modell>` in `/srv/vibedinsight/backend/.env`, `./deploy.sh restart` | 4.2, 4.3 | Abschreiben der dokumentierten Deploy-Mechanik (Faktenblatt) |
| 4.5 | Execute VPS switch | **Stefan (SSH)** — Begleitung Sonnet | VPS: Block aus 4.4 ausführen | 4.4 | SSH auf VPS ist nicht automatisierbar aus dieser Umgebung |
| 4.6 | Update model docs | Haiku | `CLAUDE.md` (Prod-Setup: neues `OLLAMA_MODEL`, alte llama3.2:1b-Historie kürzen), `DEV.md` (Dev-Modell-Empfehlung) | 4.5 | Nachziehen dokumentierter Fakten |

**Verifikation Phase 4:** 4.3 = lokale Verifikation (deutsche Summary mit dem
VPS-Kandidaten). Nach 4.5 **ohne SSH** möglich (dafür gebaut):
`GET /admin/ollama/check` → `chat_model_available: true` fürs neue Modell;
ein Prod-Ingest eines deutschen Test-Items → Summary deutsch; `GET /admin/stats`
plausibel. Latenz des Prod-Ingests messen und mit der Schätztabelle der
Recherche abgleichen (die Schätzungen sind unverifiziert — erst die Messung
macht den Entscheid endgültig).

---

## Phase 5 — Konzept-Integration in die Doku

Zwei Konzepte dauerhaft verankern. (1) Die Modell-Vorauswahl als
Arbeitsmethode. (2) Aus der Website/Admin-Blaupause NUR die übertragbaren
Querschnitts-Prinzipien — die Blaupause beschreibt eine andere Architektur
(PHP+JSON+Shared-Hosting); übernommen wird ausschließlich: **"Prod-Daten sind
das Original"** + Backup-Disziplin (§4) und **Secret-Hygiene** (§5). PHP,
JSON-als-DB, FTPS, mail(), Tracking: bewusst NICHT übernommen.

| # | Aufgabe | Modell | Scope/Dateien | Abhängigkeit | Begründung |
|---|---|---|---|---|---|
| 5.1 | CLAUDE.md section "Arbeitsweise: Modell-Routing" | Haiku | `CLAUDE.md`: kurzer Abschnitt — Legende-Tabelle (Kopf dieses Plans), Faustregel "billigstes Modell, das noch zuverlässig löst; hochstufen bei echter Logik", Verweis auf `IMPLEMENTATION-PLAN.md` als lebendes Beispiel | — | Inhalt ist hier fertig formuliert, Edit ist Übertrag |
| 5.2 | CLAUDE.md pitfall: "Prod-Daten sind das Original" | Haiku | `CLAUDE.md` (Stolperfallen), 3–4 Zeilen: VPS-Postgres ist das Original — nie mit leerem/altem Dev-Stand überschreiben; Datenfluss nur Prod→Dev (`pg_dump` vom VPS in die Dev-DB), nie umgekehrt; vor riskanten Prod-Aktionen `./deploy.sh backup` | — | Prinzip ist hier destilliert, Edit ist mechanisch |
| 5.3 | SECURITY.md: operational checklist (backup + secrets) | Haiku | `SECURITY.md`, neuer Abschnitt "Operational Practices": regelmäßiges `deploy.sh backup` + Kopie außer Haus (Backup nur auf dem VPS hilft bei VPS-Ausfall nicht) + Restore einmal getestet; `API_KEY` in Prod setzen; `.env` bleibt gitignored; Tokens nie als CLI-Argument (globale Regel) | — | Checklisten-Text nach fertiger Vorlage |

**Verifikation Phase 5:** Gegenlesen auf Ehrlichkeit — es steht NUR
Übertragbares drin (kein PHP-/JSON-/FTPS-Erbe); CLAUDE.md bleibt kompakt
(Routing-Abschnitt ≤ 15 Zeilen); keine Dopplung zwischen CLAUDE.md und
SECURITY.md (Stolperfalle kurz, Checkliste ausführlich).

---

## Phase 6 — VPS-Absicherung & Rollout-Abschluss (optional, empfohlen)

Setzt die Phase-5-Checkliste praktisch um. Alles hier braucht Stefan (SSH
bzw. App in der Hand) — Claude bereitet vor und verifiziert remote.

| # | Aufgabe | Modell | Scope/Dateien | Abhängigkeit | Begründung |
|---|---|---|---|---|---|
| 6.1 | Prepare API_KEY rollout block | Haiku | Kommandoblock: Key generieren (`openssl rand -hex 32`), `API_KEY=` in `/srv/vibedinsight/backend/.env`, `./deploy.sh restart`; Hinweis: denselben Key in den App-Einstellungen eintragen | — | Vorbereitung nach bekannter Mechanik |
| 6.2 | Set API_KEY on VPS + in app | **Stefan (SSH + App)** | Block aus 6.1 ausführen | 6.1, 4.5 | Erst nach Modellwechsel, damit nur eine Variable pro Rollout kippt |
| 6.3 | Backup + restore drill | **Stefan (SSH)** — Anleitung Sonnet | VPS: `./deploy.sh backup`; Restore-Test in die pop-os-Dev-DB (`./dev.sh psql` erreichbar auf :5433) — testet Restore UND liefert realistische Dev-Daten, ohne Prod anzufassen | 5.3 | Restore-in-Dev braucht saubere Anleitung (pg_restore gegen pgvector-DB), Rest ist Stefans Hand |

**Verifikation Phase 6:** Nach 6.2: Request ohne Key → 401/403, mit Key → 200;
App-Ingest funktioniert weiter. Nach 6.3: Dev-DB enthält Prod-Items,
`SELECT count(*) FROM content_items` plausibel, Dev-API liefert sie aus.
**Was nur Stefan kann** (klar markiert): 4.1, 4.5, 6.2, 6.3 — alles
SSH-auf-VPS bzw. App-am-Gerät. Alle Remote-Verifikationen
(`/admin/ollama/check`, `/admin/stats`, API-Key-Test) macht Claude selbst.

---

## Offene Entscheidungen ("?") — gebündelt

1. **VPS-RAM/CPU (4.1) — der einzige harte Blocker für Phase 4.**
   Stefan: `free -h` + `nproc` auf dem VPS, plus: läuft dort Nachbarlast
   (n8n, Neo4j, …)? **Empfehlung:** bei ~8 GB frei → `qwen3:4b-instruct`
   (besseres Deutsch/Instruction-Following, Apache 2.0, +0.6 GB); bei <~8 GB
   → `qwen2.5:3b` behalten (Zero-Risk, läuft schon); bei ≥16 GB → `qwen2.5:7b`.
2. **Dev-Modell-Parität (4.3).** **Empfehlung:** während Prompt-Fix und
   Modell-Entscheid lokal mit `qwen3:4b-instruct` testen (liegt auf pop-os
   schon vor — kostenloser Paritätstest), im Alltag danach wieder
   `qwen2.5:7b` (gleiche Qwen-Familie → Prompt-Verhalten überträgt sich;
   mehr Qualität beim Entwickeln). Homeserver müsste für Parität
   `qwen3:4b-instruct` einmal pullen — nur nötig, falls dort am Prompt
   gearbeitet wird.
3. **Docker-Aufräumen (1.5).** Erst Inventarliste (1.4), dann entscheidet
   Stefan pro Eintrag. **Empfehlung:** nur eindeutig Verwaistes (dangling
   images, gestoppte Einweg-Container) löschen, keine Volumes ohne
   Einzelfreigabe.
4. **Summary-Sprache immer Deutsch?** Betrifft 3.1: auch englische Artikel
   bekämen deutsche Summaries. **Empfehlung: ja** — Single-User, deutscher
   Nutzer, konsistente Digest-Sprache; die Quelle bleibt ja als `raw_text`
   erhalten. (Wird ohne Widerspruch als bestätigt behandelt.)

## Kostenhinweis

Verteilung der 23 Aufgaben: **Haiku 15** (Doku, Prompt, Kommandoblöcke,
Verifikations-Roundtrips), **Sonnet 3** (Container-Recreate, Prompt-Tuning-
Fallback, Modellvergleich; dazu Sonnet-Begleitung bei 4.5/6.3), **Opus 0**,
**Fable 0** (Strategieanteil steckt bereits in diesem Plan), **?/Stefan 5**
(2 Entscheidungen: 1.5 Prune-Freigabe, 4.1 RAM-Messung als Entscheid-Input;
3 SSH/Gerät: 4.5, 6.2, 6.3). Der Löwenanteil läuft auf Haiku — genau
der Hebel der Modell-Vorauswahl: die teure Denkarbeit ist mit diesem Dokument
erledigt; die Ausführung ist überwiegend billige, klar umrissene Arbeit.

---

*Erstellt 2026-07-19 per Modell-Vorauswahl (Fable 5). Etiketten bei Bedarf
während der Ausführung nachziehen — dieses Dokument ist die Single Source of
Truth fürs Modell-Routing dieser Arbeitspakete.*
