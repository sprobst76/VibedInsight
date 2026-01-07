Wenn **Android (und idealerweise iOS)** dabei sein soll, würde ich die Architektur so bauen, dass du **eine mobile App als „Capture & Read“-Client** hast und im Backend die **Ingestion/AI/Knowledge-Services** laufen. Dann kannst du später UI-Clients austauschen (Web, Mobile, Desktop), ohne alles neu zu bauen.

## Empfehlung: 3-Schichten-Architektur

### 1) Clients

**A) Mobile App (Primary)**

* **Flutter** (meine Empfehlung für dich, weil du eh schon Flutter-Erfahrung/Projekte hast)

  * 1 Codebase: Android + iOS + optional Web
  * Sehr gut für “Share into App”, Offline-Caching, schnelle UI
* Alternativen:

  * **React Native** (JS/TS, starkes Ökosystem)
  * **Kotlin Multiplatform** (wenn du sehr “native” willst, aber mehr Komplexität)

**B) Web-UI (Admin/Dashboard)**

* Für den Start: **Streamlit** (schnell, MVP)
* Später: **React/Next.js** (schöner, skalierbarer, mobilfreundlicher)

> Mobile ist für „sammeln + konsumieren“, Web ist für „organisieren + Power-Features“.

---

### 2) Backend (API & Workflows)

**FastAPI (Python)**

* Gründe: leichtgewichtig, schnell, perfekt für AI-Pipelines und deinen Python-Stack
* Endpoints:

  * `/items` (CRUD)
  * `/ingest/url`, `/ingest/text`, `/ingest/file`
  * `/summarize/{id}`
  * `/topics`, `/search`
  * `/jobs/{id}` (Status)

**Async Jobs / Queue**

* **Celery + Redis** (bewährt) oder **RQ** (super simpel)
* Jobs: Text extrahieren, LLM Summaries, Embeddings, Topic-Assign, Graph Updates

**Automationen**

* **n8n** optional für Newsletter/Mailflows & “if this then that”
* Alternativ komplett Python (weniger Komponenten)

---

### 3) Datenhaltung (bewusst getrennt)

**Metadaten / User-Daten**

* **PostgreSQL** (produktionstauglich, zuverlässig)
* Im MVP ginge SQLite, aber mit Mobile Sync + Multi-User ist Postgres der klare Winner.

**Vektorsuche (semantisch)**

* **Qdrant** (sehr gute DX, schlank, Docker-friendly)
* Alternativen: Weaviate, pgvector (wenn du “alles in Postgres” willst)

**Dokumente / Rohtexte**

* Start: Dateisystem (volume)
* Später/Cloud: S3-kompatibel (MinIO)

**Optional Knowledge Graph**

* **Neo4j** nur in der “Pro”-Variante:

  * Entitäten, Beziehungen, “widerspricht/ergänzt”, Pfad-Abfragen, Kontextnetze
* Alternative Graph ohne Neo4j:

  * “Pseudo-Graph” in Postgres (Join-Tabellen) + Qdrant Similarity (leichter, aber weniger mächtig)

---

## Mobile App: Welche Features technisch wichtig sind

### Capture (der Killer-Usecase)

* **Android Share Sheet**: “Teilen → VibedInsight”
* In-App “Save Link”, “Paste Text”, “Upload PDF”
* Optional: Browser Extension später (für Desktop)

### Offline First (sehr wichtig auf Mobile)

* Lokal: **SQLite** (drift/sqflite) oder **Hive** (Key-Value)
* Sync-Strategie:

  * “Write-ahead” lokal → später push
  * Konflikte: last-write-wins für Tags/Notes (reicht am Anfang)

### Push & Background Jobs

* Push: **Firebase Cloud Messaging (FCM)**
* Hintergrund: “Summary fertig”, “Weekly Digest verfügbar”

### Auth

* Für dein Self-hosting: am einfachsten

  * **Auth via JWT** (FastAPI)
  * oder **Keycloak** (wenn du SSO/mehr Nutzer willst)
* Für “nur du”: Token-Login + optional Passkey später

---

## Zwei konkrete “Stacks” zur Auswahl

### Stack A: Schlank & schnell (MVP → gut erweiterbar)

* Flutter App (Android/iOS)
* FastAPI
* Postgres
* Qdrant (optional ab Phase 2)
* Celery + Redis
* Ollama lokal + optional Azure OpenAI

**Warum gut:** wenig Teile, trotzdem professionell.

### Stack B: Pro / Knowledge Platform

* Flutter App + Web (Next.js)
* FastAPI
* Postgres + S3/MinIO
* Qdrant
* Neo4j
* Celery + Redis
* n8n für Ingestion-Automationen

**Warum gut:** Beziehungen/Graph-Exploration, “Second Brain” richtig ausgebaut.

---

## Wie ich starten würde (ohne Overengineering)

1. **Flutter App**: Share → Inbox (nur Link/Text) + Login
2. **FastAPI**: Ingest + Item speichern
3. **Background Job**: Summary + Topics
4. **UI**: Detailseite zeigt Summary, Topics, Tags
5. **Semantische Suche**: Qdrant dazu
6. **Erst dann** Neo4j (wenn du merkst, dass “Beziehungen” dein echter Mehrwert sind)

---

Wenn du mir 2 Entscheidungen gibst, lege ich dir daraus eine sehr konkrete Starter-Struktur (Repo + docker-compose + Datenmodell + API-Routen + Flutter Screens) fest:

* Willst du **Multi-User** oder “nur Stefan”?
* Soll die App **offline** voll nutzbar sein oder reicht “online-first”?
