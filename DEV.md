# VibedInsight — Development Setup (development-homeserver)

Development happens on the **development-homeserver** (Tailscale:
`development-homeserver`), which runs Docker + Ollama and has the Android
test phone attached via USB. Production stays on the VPS and deploys
automatically on push to `main` — nothing in this document touches prod.

**Git is the single source of truth.** Clone from GitHub; do NOT rsync
project trees between machines (`sync-from-homeserver.sh` is legacy and can
overwrite work).

## One-time bootstrap on the homeserver

```bash
# If an old pre-0.4.0 copy exists, move it aside first:
[ -d ~/development/VibedInsight ] && mv ~/development/VibedInsight ~/development/VibedInsight.pre-0.4-backup

git clone git@github.com:sprobst76/VibedInsight.git ~/development/VibedInsight
cd ~/development/VibedInsight
./dev.sh up
```

`dev.sh up` writes a `backend/.env` with dev defaults on first run, builds
the stack from `backend/docker-compose.dev.yml` and waits for `/health`.

Required Ollama models on the homeserver (the backend auto-pulls a missing
chat model, the embedding model must be pulled manually):

```bash
ollama pull llama3.2:3b
ollama pull mxbai-embed-large
```

## Dev stack layout

| Service | Container | Host port | Notes |
|---|---|---|---|
| API | `vibedinsight-dev-api` | `8100` | uvicorn `--reload`, source volume-mounted |
| Postgres | `vibedinsight-dev-postgres` | `5433` | pgvector, data in `backend/data/postgres-dev/` |

- Ollama is reached at `http://host.docker.internal:11434` (host-gateway).
  ⚠️ If a legacy `backend/.env` sets `OLLAMA_BASE_URL=http://localhost:11434`,
  the container can't reach it — keep the `host.docker.internal` URL.
- `ALLOW_PRIVATE_URLS=true` and `WEEKLY_AUTO_GENERATE=false` by default in dev.
- Ports/models are overridable in `backend/.env`
  (`DEV_API_PORT`, `DEV_DB_PORT`, `OLLAMA_MODEL`, …).

## Daily commands

```bash
./dev.sh up        # build + start + health check
./dev.sh logs      # follow API logs (./dev.sh logs postgres for the DB)
./dev.sh test      # backend pytest against a separate vibedinsight_test DB
./dev.sh psql      # psql into the dev database
./dev.sh down      # stop the stack
```

`./dev.sh test` never touches the dev database: the test suite runs the
full migration chain (which drops tables), so it gets its own
`vibedinsight_test` database inside the same Postgres container.

## Flutter app against the dev backend

The app reads server URL + API key from its settings screen, so no code
changes are needed:

1. `cd app && flutter run` (phone attached to the homeserver via USB/WiFi-ADB).
   ⚠️ Flutter (3.38.5) is located at `~/flutter/bin`; in non-interactive shells
   it's not in `PATH` — prepend `export PATH="$HOME/flutter/bin:$PATH"` if needed.
2. In the app settings, set the server URL to
   `http://<homeserver-LAN-or-Tailscale-IP>:8100` (dev `API_KEY` is empty by
   default — leave the key field blank).

Working from another machine against the homeserver's phone: forward the
ADB server over SSH and point local tools at it:

```bash
ssh -N -L 5037:localhost:5037 development-homeserver &
ADB_SERVER_SOCKET=tcp:localhost:5037 adb devices
```

## Dev on pop-os (local machine)

The same `./dev.sh` workflow runs on pop-os with identical ports (:8100 API,
:5433 pgvector). `docker compose up` brings up the stack. Ollama runs as a
Docker container (part of the `ai-lab` stack) → pull models via
`docker exec ollama ollama pull ...` or directly via the HTTP API on `:11434`.
The same `OLLAMA_BASE_URL=http://host.docker.internal:11434` applies here.

**Updating Ollama itself** (the container is part of the shared `ai-lab`
stack — a brief restart affects every ai-lab service, e.g. mindcraft/openwebui;
the models survive because they live in the `/srv/ai-lab/data/ollama` bind
mount):

```bash
docker compose -f /srv/ai-lab/docker-compose.yml pull ollama
docker compose -f /srv/ai-lab/docker-compose.yml up -d ollama   # recreates only the ollama service
```

Verify: `curl -s localhost:11434/api/version`, `docker exec ollama ollama list`
(models still present), then one dev-stack ingest roundtrip (Summary + Topics +
Embedding). Do NOT `docker run` a fresh container by hand — that detaches it
from the compose stack and drops the GPU/port/mount config.
(Verified 2026-07-19: 0.13.5 → 0.32.1, pipeline intact.)

## Ops: URL-Rehash (after v0.7)

v0.7 changed URL normalisation (the query string is now part of the dedup
hash), so existing `url_hash` values must be recomputed once. Manual step,
never run at container start. Source: `backend/app/tools/rehash.py`.

1. Back up first: `./deploy.sh backup`.
2. Dry run (the default; writes nothing):
   ```bash
   docker compose exec api python -m app.tools.rehash --dry-run --report /tmp/rehash.csv
   ```
3. Check the report and the printed collision groups. Only after Stefan has
   approved, apply (one transaction, nothing is deleted):
   ```bash
   docker compose exec api python -m app.tools.rehash --apply --report /tmp/rehash.csv
   ```
   In a collision group the oldest item stays canonical and keeps the new
   hash. Younger duplicates are kept, not deleted, and get the marker hash
   `<first 23 hex chars>:dup:<uuid>` (23 + 5 + 36 = 64 chars, the `url_hash`
   column limit).
4. A second run is idempotent: it finds every item already at its target hash
   and changes nothing.

**Known limits:**
- URLs that were wrongly deduplicated under the old normalisation (e.g. a
  second YouTube video with a different `v=` parameter) cannot be restored by
  the rehash. They have to be shared again.
- Until the rehash has run, a link that was already saved and is shared again
  with a query string can be created as a duplicate.

## Prod deploy

Push to Gitea `main` → Gitea Actions runner on the VPS → `deploy.sh update`
(see `ops/GITEA-DEPLOY.md`).
Branches `rework/**` run CI without deploying.

## App size and startup (measured 2026-10-14, v0.7.0)

`flutter build apk --release --split-per-abi` (CI does this since v0.7.0):

| APK | Size |
|---|---|
| fat (all ABIs, old CI default) | 58.5 MB |
| arm64-v8a (main sideload APK) | 21.5 MB |
| armeabi-v7a | 19.4 MB |
| x86_64 (emulator only, not published) | 22.9 MB |

Motorola Defy (Android 11), release build, `am start -W` cold start: 605–738 ms
(median of 4 warm-cache runs; 1.27 s right after install), PSS ≈ 100 MB.
R8 and resource shrinking were already enabled. Decision: no Kotlin rewrite —
revisit only if cold start exceeds ~1.5 s.

Side-by-side device tests: debug builds use the application id suffix `.dev`;
for a release-like build run `VI_DEV_SUFFIX=1 flutter build apk --release --split-per-abi`
and install with `adb install -r` (package `com.vibedinsight.app.dev`; the real app and
its settings stay untouched).
