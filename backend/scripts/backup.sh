#!/bin/bash
#
# VibedInsight Database Backup Script
#
# Usage:
#   ./backup.sh              # Create backup
#   ./backup.sh --restore    # Restore from latest backup
#   ./backup.sh --restore <file>  # Restore from specific backup
#   ./backup.sh --list       # List available backups
#
# Cron example (daily at 3 AM):
#   0 3 * * * /srv/vibedinsight/backend/scripts/backup.sh >> /var/log/vibedinsight-backup.log 2>&1
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$BACKEND_DIR/backups}"
CONTAINER_NAME="vibedinsight-postgres"
DB_NAME="vibedinsight"
DB_USER="vibedinsight"
KEEP_BACKUPS=7  # Number of backups to keep

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Check if postgres container is running
check_container() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        error "Container '$CONTAINER_NAME' is not running"
        exit 1
    fi
}

# Create backup
create_backup() {
    check_container

    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    BACKUP_FILE="$BACKUP_DIR/vibedinsight_${TIMESTAMP}.sql.gz"

    log "Creating backup: $BACKUP_FILE"

    # Create backup using pg_dump
    docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

    if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
        SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        success "Backup created: $BACKUP_FILE ($SIZE)"

        # Rotate old backups
        rotate_backups
    else
        error "Backup failed or file is empty"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
}

# Rotate old backups (keep only KEEP_BACKUPS most recent)
rotate_backups() {
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/vibedinsight_*.sql.gz 2>/dev/null | wc -l)

    if [ "$BACKUP_COUNT" -gt "$KEEP_BACKUPS" ]; then
        DELETE_COUNT=$((BACKUP_COUNT - KEEP_BACKUPS))
        log "Rotating backups: removing $DELETE_COUNT old backup(s)"

        ls -1t "$BACKUP_DIR"/vibedinsight_*.sql.gz | tail -n "$DELETE_COUNT" | while read -r file; do
            rm -f "$file"
            log "Deleted: $(basename "$file")"
        done
    fi
}

# List available backups
list_backups() {
    log "Available backups in $BACKUP_DIR:"
    echo ""

    if ls "$BACKUP_DIR"/vibedinsight_*.sql.gz 1>/dev/null 2>&1; then
        ls -lh "$BACKUP_DIR"/vibedinsight_*.sql.gz | awk '{print "  " $9 " (" $5 ")"}'
    else
        warn "No backups found"
    fi
}

# Restore from backup
restore_backup() {
    check_container

    BACKUP_FILE="$1"

    # If no file specified, use latest
    if [ -z "$BACKUP_FILE" ]; then
        BACKUP_FILE=$(ls -1t "$BACKUP_DIR"/vibedinsight_*.sql.gz 2>/dev/null | head -1)
        if [ -z "$BACKUP_FILE" ]; then
            error "No backup files found in $BACKUP_DIR"
            exit 1
        fi
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    warn "This will OVERWRITE the current database!"
    warn "Backup file: $BACKUP_FILE"
    echo ""
    read -p "Are you sure? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled"
        exit 0
    fi

    log "Creating safety backup before restore..."
    SAFETY_BACKUP="$BACKUP_DIR/pre_restore_$(date '+%Y%m%d_%H%M%S').sql.gz"
    docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$SAFETY_BACKUP"
    success "Safety backup: $SAFETY_BACKUP"

    log "Restoring from: $BACKUP_FILE"

    # Drop and recreate database
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

    # Restore
    gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"

    success "Database restored successfully!"
    log "Restarting API container to reconnect..."

    # Restart API to reconnect
    cd "$BACKEND_DIR" && docker compose restart api

    success "Restore complete!"
}

# Main
case "${1:-}" in
    --restore)
        restore_backup "$2"
        ;;
    --list)
        list_backups
        ;;
    --help|-h)
        echo "VibedInsight Database Backup Script"
        echo ""
        echo "Usage:"
        echo "  $0              Create a new backup"
        echo "  $0 --restore    Restore from latest backup"
        echo "  $0 --restore <file>  Restore from specific file"
        echo "  $0 --list       List available backups"
        echo "  $0 --help       Show this help"
        echo ""
        echo "Environment variables:"
        echo "  BACKUP_DIR      Override backup directory (default: ./backups)"
        echo "  KEEP_BACKUPS    Number of backups to keep (default: 7)"
        ;;
    *)
        create_backup
        ;;
esac
