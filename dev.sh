#!/bin/bash
# VibedInsight development stack helper (see DEV.md).
# Runs the self-contained dev stack from backend/docker-compose.dev.yml.
# Usage: ./dev.sh [up|down|restart|logs|status|test|psql]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
COMPOSE=(docker compose -f "$BACKEND_DIR/docker-compose.dev.yml" --project-directory "$BACKEND_DIR")

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

ensure_env() {
    if [[ ! -f "$BACKEND_DIR/.env" ]]; then
        log_info "Creating dev .env..."
        cat > "$BACKEND_DIR/.env" <<'EOF'
# VibedInsight dev environment (used by docker-compose.dev.yml)
DEV_POSTGRES_PASSWORD=vibedinsight
DEV_DB_PORT=5433
DEV_API_PORT=8100
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_EMBEDDING_MODEL=mxbai-embed-large
# Empty = API runs without auth (fine for dev inside the LAN)
API_KEY=
EOF
        log_info "Wrote $BACKEND_DIR/.env — adjust ports/models if needed."
    fi
}

up() {
    ensure_env
    log_info "Building and starting dev stack..."
    "${COMPOSE[@]}" up -d --build
    wait_healthy
    status
    local port
    port=$(grep -oP '^DEV_API_PORT=\K.*' "$BACKEND_DIR/.env" 2>/dev/null || true)
    log_info "API: http://localhost:${port:-8100} (docs: /docs)"
}

wait_healthy() {
    log_info "Waiting for API health..."
    for _ in $(seq 1 24); do
        if "${COMPOSE[@]}" exec -T api curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_info "API is healthy."
            return 0
        fi
        sleep 5
    done
    log_error "API did not become healthy. Check: ./dev.sh logs"
    exit 1
}

status() {
    "${COMPOSE[@]}" ps
}

logs() {
    "${COMPOSE[@]}" logs -f --tail=100 "${1:-api}"
}

run_tests() {
    # Tests run their own migration chain, which DROPS tables — never point
    # them at the dev database. They get a dedicated vibedinsight_test DB.
    local pw
    pw=$(grep -oP '^DEV_POSTGRES_PASSWORD=\K.*' "$BACKEND_DIR/.env" 2>/dev/null || true)
    pw="${pw:-vibedinsight}"

    log_info "Ensuring test database exists..."
    "${COMPOSE[@]}" exec -T postgres sh -c \
        "psql -U vibedinsight -tc \"SELECT 1 FROM pg_database WHERE datname='vibedinsight_test'\" | grep -q 1 \
         || createdb -U vibedinsight vibedinsight_test"

    log_info "Running backend tests (pytest inside the api container)..."
    "${COMPOSE[@]}" exec -T api sh -c \
        'pip install -q -e ".[dev]" \
         && DATABASE_URL=postgresql+asyncpg://vibedinsight:'"$pw"'@postgres:5432/vibedinsight_test \
            python -m pytest tests/ -q'
}

psql_shell() {
    "${COMPOSE[@]}" exec postgres psql -U vibedinsight vibedinsight
}

case "${1:-}" in
    up) up ;;
    down) "${COMPOSE[@]}" down ;;
    restart) "${COMPOSE[@]}" restart ;;
    logs) logs "${2:-}" ;;
    status) status ;;
    test) run_tests ;;
    psql) psql_shell ;;
    *)
        echo "Usage: $0 [up|down|restart|logs [service]|status|test|psql]"
        exit 1
        ;;
esac
