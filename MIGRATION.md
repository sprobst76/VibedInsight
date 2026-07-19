# Migration: Entwicklung auf den development-homeserver (2026-07-19)

Dokumentation des Umzugs der VibedInsight-**Entwicklung** von der lokalen
Maschine (pop-os) auf den `development-homeserver`. Die **Produktion** bleibt
unverändert auf dem VPS.

## Ausgangslage & Ziel

VibedInsight wurde bis dahin lokal entwickelt und lief in Produktion auf dem
VPS. Ziel war, die Entwicklung auf den `development-homeserver` zu verlegen —
dort stehen mehr Rechenleistung, das native Ollama und das per USB
angeschlossene Test-Smartphone (`ZY32CVNR2B`). Prod sollte unberührt
weiterlaufen.

Der Umzug bestand aus zwei unabhängigen Teilen:
- **A** — das Projekt selbst mit einem lauffähigen Dev-Stack
- **B** — die persönliche Claude-Code-Arbeitsumgebung

**Grundprinzip:** Git/GitHub ist die einzige Quelle der Wahrheit. Es werden
keine Projektbäume mehr per rsync synchronisiert (`sync-from-homeserver.sh`
ist Legacy). Prod-Deploy bleibt: Push auf `main` → GitHub Action → VPS.

## Teil A — VibedInsight-Dev-Stack

### Neu gebaut (Commit `413ea98`, rein additiv — CI + VPS-Deploy blieben grün)

| Datei | Zweck |
|---|---|
| `backend/docker-compose.dev.yml` | Eigenständiger Dev-Stack: pgvector auf **:5433**, API auf **:8100** mit `uvicorn --reload` und gemountetem Quellcode. Kein Traefik, kein externes Netz. Ollama über `host.docker.internal`. |
| `dev.sh` | Helfer: `up/down/logs/status/psql/test`. `test` legt automatisch eine separate `vibedinsight_test`-DB an (die Migrationskette droppt Tabellen → Dev-Daten bleiben unangetastet). |
| `DEV.md` | Homeserver-Anleitung inkl. App-gegen-Dev-Backend und Remote-ADB. |

### Ausrollen auf dem Homeserver

1. **Bestandsaufnahme:** Ordner existierte bereits (14 Commits hinterher,
   sauber), Docker 29.6.1 + ADB vorhanden, Ports 5433/8100 frei, Ollama
   lauscht auf `0.0.0.0:11434`.
2. `git pull` brachte das Repo auf Stand.
3. Dev-`.env` geschrieben mit **`OLLAMA_MODEL=qwen2.5:7b`** (statt des
   schwächeren VPS-Modells — lag auf dem Homeserver bereits vor).
4. Embedding-Modell **`mxbai-embed-large`** gepullt. Muss exakt sein: die
   pgvector-Spalte ist auf `Vector(1024)` festgelegt; die dort vorhandenen
   768-dim-Modelle (`embeddinggemma`, `nomic`) passen **nicht**.
5. `./dev.sh up` — Image gebaut, Migrationen gelaufen, beide Container
   `healthy`, Autostart via `restart: unless-stopped`.

### Verifikation

Ein Test-Item lief komplett durch die Pipeline: Summary erzeugt (qwen2.5:7b),
drei sauber normalisierte deutsche Topics (`postgres-erweiterung`,
`vektor-suche`, `semantische-suche`), ein Embedding in pgvector. Der kritische
Punkt — API erreicht Ollama aus dem Container heraus — wurde per
`/admin/ollama/check` bestätigt (`chat_model_available` +
`embedding_model_available` = true).

## Teil B — Claude-Code-Umgebung

Die `~/.claude`-Umgebung ist umfangreich (globale Regeln, GSD-Framework mit
Hooks, 33 Agents, 72 Skills, Plugins) und teils maschinenspezifisch. Statt
vieler Einzelkommandos übernahm ein **idempotentes Migrations-Skript** den
Transfer. Es:

1. **sichert die bestehende Homeserver-Config** (`~/.claude.backup-<ts>`) —
   non-destruktiv, Rollback jederzeit möglich;
2. **überträgt nur die portablen Teile** — globale `CLAUDE.md`,
   GSD-Framework, Skills, Agents, Hooks, Plugins, Settings, das
   VibedInsight-Memory und die Android-Skripte
   (`~/development/WorkflowAnalyser/scripts/`);
3. **lässt den Login bewusst aus** (`.credentials.json`) — der Homeserver
   hatte bereits einen gültigen Login, ein Neu-Einloggen war nicht nötig;
4. **schließt fremde Projekt-Historien und Caches aus** (kein 1:1-Klon
   device-spezifischer Daten);
5. **korrigiert den hartkodierten node-Pfad in `settings.json`** — die Hooks
   zeigten auf eine nvm-Version, die es dort nicht gab; das Skript schrieb
   sie auf die vorhandene `v24.11.1` um (User + Home sind auf beiden
   Maschinen `spro`/`/home/spro`, daher passten alle übrigen Pfade 1:1).

### Verifikation

Ein headless-Rauchtest (`claude -p "Antworte nur mit: MIGRATION OK"` im
Projektverzeichnis auf dem Homeserver) lieferte `MIGRATION OK` — Claude
startet mit der migrierten Konfiguration inklusive SessionStart-Hooks sauber
hoch, ohne zu blockieren.

## Ergebnis

Auf dem Homeserver läuft ein eigenständiger, verifizierter Dev-Stack, und die
komplette Claude-Umgebung ist einsatzbereit. Der Kontext (`DEV.md`, Projekt-
`CLAUDE.md`, Memory) ist mit umgezogen, sodass eine frische Session dort
nahtlos weiterarbeiten kann. Die lokale Maschine blieb unverändert — es wurde
nichts gelöscht.

## Offen geblieben (bewusst)

- `claude update` auf dem Homeserver (2.1.58 → aktuell) — reine Kür.
- **Flutter fehlt auf dem Homeserver** (nur `adb` vorhanden) — SDK nachinstallieren
  (App-Builds direkt dort) *oder* App vom Laptop gegen `http://<homeserver>:8100`
  bauen (ADB per SSH-Forward, siehe `DEV.md`). Pop-os hat Flutter 3.38.5
  unter `~/flutter/bin`.
- **Prod-Daten nicht kopiert** — der Dev-Stack startet leer. Bei Bedarf einen
  `pg_dump` vom VPS in die Dev-DB einspielen.
- ~~**Backlog:** Der `summary`-Prompt erzwingt keine Sprache → Summaries kommen
  z.T. englisch trotz deutschem Input.~~ **Behoben in 0.4.1** (2026-07-19):
  Prompt auf Deutsch umgeschrieben, Ausgabesprache erzwungen (verifiziert).
