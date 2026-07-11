#!/bin/bash
# VibedInsight Deployment Script
# Usage: ./deploy.sh [install|update|logs|status|backup|restart]

set -e

# Configuration
REPO_URL="https://github.com/sprobst76/VibedInsight.git"
INSTALL_DIR="/srv/vibedinsight"
BACKEND_DIR="$INSTALL_DIR/backend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as correct user
check_user() {
    if [[ $EUID -eq 0 ]]; then
        log_error "Don't run as root. Use your regular user."
        exit 1
    fi
}

# Initial installation
install() {
    log_info "Installing VibedInsight..."

    if [[ -d "$INSTALL_DIR" ]]; then
        log_error "$INSTALL_DIR already exists. Use 'update' instead."
        exit 1
    fi

    # Clone repository
    log_info "Cloning repository..."
    cd /srv
    git clone "$REPO_URL" vibedinsight

    # Setup environment
    cd "$BACKEND_DIR"
    if [[ ! -f .env ]]; then
        log_info "Creating .env file..."
        cp .env.example .env

        # Generate secure password and API key
        POSTGRES_PW=$(openssl rand -base64 24)
        sed -i "s/CHANGE_ME_TO_SECURE_PASSWORD/$POSTGRES_PW/" .env
        API_KEY=$(openssl rand -hex 32)
        sed -i "s/CHANGE_ME_TO_RANDOM_API_KEY/$API_KEY/" .env
        log_info "Generated API key (needed in the app): $API_KEY"

        log_warn "Edit .env to set your DOMAIN:"
        log_warn "  nano $BACKEND_DIR/.env"
        echo ""
        read -p "Enter your domain (e.g., example.com): " DOMAIN
        sed -i "s/your-domain.com/$DOMAIN/" .env
    fi

    # Build and start (the container entrypoint runs alembic upgrade head)
    log_info "Building and starting containers..."
    docker compose up -d --build

    # Wait until healthy
    wait_healthy

    # Check status
    status

    log_info "Installation complete!"
    log_info "API available at: https://insight.lab.$DOMAIN"
    log_info "Swagger UI at: https://insight.lab.$DOMAIN/docs"
}

# Wait for API to become healthy (retries for up to 120s).
# NOTE: the api container has no host port mapping (Traefik network only),
# so the check must run inside the container.
wait_healthy() {
    log_info "Waiting for API to become healthy..."
    for i in $(seq 1 24); do
        if docker compose exec -T api curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "  API: ${GREEN}healthy${NC} (after ${i}×5s)"
            return 0
        fi
        echo "  Attempt $i/24 — not ready yet, waiting 5s..."
        sleep 5
    done
    log_error "API did not become healthy within 120s!"
    docker compose logs --tail=80 api
    log_error "Rollback: restore the pre-deploy backup and 'git checkout' the previous commit."
    return 1
}

# Update existing installation
update() {
    log_info "Updating VibedInsight..."

    if [[ ! -d "$INSTALL_DIR" ]]; then
        log_error "$INSTALL_DIR does not exist. Use 'install' first."
        exit 1
    fi

    cd "$INSTALL_DIR"

    # Backup database before any changes
    log_info "Creating pre-deploy backup..."
    cd "$BACKEND_DIR"
    BACKUP_FILE="backup_predeploy_$(date +%Y%m%d_%H%M%S).sql"
    if docker compose exec -T postgres pg_isready -U vibedinsight > /dev/null 2>&1; then
        docker compose exec -T postgres pg_dump -U vibedinsight vibedinsight > "$BACKUP_FILE"
        if [[ ! -s "$BACKUP_FILE" ]]; then
            log_error "Backup file is empty — aborting deploy!"
            rm -f "$BACKUP_FILE"
            exit 1
        fi
        log_info "Backup saved: $BACKEND_DIR/$BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
        # Keep only the last 5 pre-deploy backups
        ls -t backup_predeploy_*.sql 2>/dev/null | tail -n +6 | xargs -r rm -f
    else
        log_warn "PostgreSQL not reachable — skipping backup"
    fi

    # Pull latest changes
    cd "$INSTALL_DIR"
    log_info "Pulling latest changes..."
    git pull

    # Rebuild and restart (postgres too, in case its image changed;
    # the api entrypoint runs `alembic upgrade head` before starting)
    cd "$BACKEND_DIR"
    log_info "Rebuilding API container..."
    docker compose build --no-cache api
    docker compose up -d

    # Wait until healthy
    wait_healthy

    # Cleanup old images
    log_info "Cleaning up old images..."
    docker image prune -f

    # Check status
    status

    log_info "Update complete!"
}

# Show logs
logs() {
    cd "$BACKEND_DIR"
    docker compose logs -f --tail=100 "${1:-api}"
}

# Show status
status() {
    log_info "Service Status:"
    cd "$BACKEND_DIR"
    docker compose ps

    echo ""
    log_info "Health Check:"
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  API: ${GREEN}healthy${NC}"
    else
        echo -e "  API: ${RED}unhealthy${NC}"
    fi

    if docker compose exec -T postgres pg_isready -U vibedinsight > /dev/null 2>&1; then
        echo -e "  PostgreSQL: ${GREEN}healthy${NC}"
    else
        echo -e "  PostgreSQL: ${RED}unhealthy${NC}"
    fi
}

# Backup database
backup() {
    log_info "Creating database backup..."
    cd "$BACKEND_DIR"

    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    docker compose exec -T postgres pg_dump -U vibedinsight vibedinsight > "$BACKUP_FILE"

    log_info "Backup saved to: $BACKEND_DIR/$BACKUP_FILE"
    ls -lh "$BACKUP_FILE"

    # Keep only last 10 backups
    BACKUP_COUNT=$(ls backup_*.sql 2>/dev/null | wc -l)
    if [[ "$BACKUP_COUNT" -gt 10 ]]; then
        log_info "Removing old backups (keeping last 10)..."
        ls -t backup_*.sql | tail -n +11 | xargs rm -f
    fi
}

# Restart services
restart() {
    log_info "Restarting services..."
    cd "$BACKEND_DIR"
    docker compose restart
    status
}

# Stop services
stop() {
    log_info "Stopping services..."
    cd "$BACKEND_DIR"
    docker compose down
}

# Show help
help() {
    echo "VibedInsight Deployment Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install   - Initial installation (clone, configure, start)"
    echo "  update    - Pull latest changes and rebuild"
    echo "  logs      - Show logs (default: api, or specify service)"
    echo "  status    - Show service status and health"
    echo "  backup    - Create database backup"
    echo "  restart   - Restart all services"
    echo "  stop      - Stop all services"
    echo "  help      - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 install          # First-time setup"
    echo "  $0 update           # Deploy latest version"
    echo "  $0 logs             # View API logs"
    echo "  $0 logs postgres    # View database logs"
}

# Main
check_user

case "${1:-help}" in
    install) install ;;
    update)  update ;;
    logs)    logs "$2" ;;
    status)  status ;;
    backup)  backup ;;
    restart) restart ;;
    stop)    stop ;;
    help)    help ;;
    *)       log_error "Unknown command: $1"; help; exit 1 ;;
esac
