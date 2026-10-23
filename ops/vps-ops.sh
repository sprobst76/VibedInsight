#!/bin/bash
# Forced-command dispatcher for the restricted "vi-ops" SSH key.
# Only the exact commands below are allowed; everything else is rejected.
# Nothing from $SSH_ORIGINAL_COMMAND is ever evaluated or interpolated.
set -u

BACKEND_DIR="${VI_BACKEND_DIR:-/srv/vibedinsight/backend}"
DOCKER="${VI_DOCKER:-docker}"

cd "$BACKEND_DIR" || { echo "backend dir not found: $BACKEND_DIR" >&2; exit 1; }

case "${SSH_ORIGINAL_COMMAND:-}" in
  health)
    "$DOCKER" compose exec -T api curl -s localhost:8000/health; echo ;;
  status)
    "$DOCKER" compose ps ;;
  logs)
    "$DOCKER" compose logs --tail 200 api ;;
  rehash-dry-run)
    "$DOCKER" compose exec -T api python -m app.tools.rehash --dry-run --report /tmp/rehash.csv ;;
  deploy-info)
    # Read-only: where the checkout pulls from, what is checked out, pre-deploy backups, runner state
    ROOT="$(dirname "$BACKEND_DIR")"
    echo "origin:  $(git -C "$ROOT" remote get-url origin 2>&1)"
    echo "HEAD:    $(git -C "$ROOT" log -1 --format='%h %ad %s' --date=iso 2>&1)"
    echo "runner:  $(systemctl is-active act_runner-vibedinsight 2>&1)"
    echo "backups:"
    ls -l --time-style=long-iso "$BACKEND_DIR"/backup_predeploy_*.sql 2>/dev/null \
      | awk '{print "  " $6, $7, $5 " bytes", $8}' || true ;;
  rehash-report)
    "$DOCKER" compose exec -T api cat /tmp/rehash.csv ;;
  *)
    echo "not allowed: ${SSH_ORIGINAL_COMMAND:-<interactive shell>}" >&2
    echo "allowed: health status logs deploy-info rehash-dry-run rehash-report" >&2
    exit 126 ;;
esac
