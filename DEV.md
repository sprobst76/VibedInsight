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
2. In the app settings, set the server URL to
   `http://<homeserver-LAN-or-Tailscale-IP>:8100` (dev `API_KEY` is empty by
   default — leave the key field blank).

Working from another machine against the homeserver's phone: forward the
ADB server over SSH and point local tools at it:

```bash
ssh -N -L 5037:localhost:5037 development-homeserver &
ADB_SERVER_SOCKET=tcp:localhost:5037 adb devices
```

## Prod deploy (unchanged)

Push to `main` → GitHub Action → SSH to VPS → `deploy.sh update`.
Branches `rework/**` run CI without deploying.
