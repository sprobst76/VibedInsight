#!/bin/bash
# Offline test of vps-ops.sh with a fake docker binary. Safe to run anywhere.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/backend"
cat > "$TMP/docker" <<'F'
#!/bin/bash
echo "$*" >> "$VI_FAKE_LOG"
echo "fake-docker-ok"
F
chmod +x "$TMP/docker"
export VI_BACKEND_DIR="$TMP/backend" VI_DOCKER="$TMP/docker" VI_FAKE_LOG="$TMP/log"
pass=0; fail=0
ok()   { pass=$((pass+1)); echo "  ok   $1"; }
bad()  { fail=$((fail+1)); echo "  FAIL $1"; }
run()  { : > "$VI_FAKE_LOG"; SSH_ORIGINAL_COMMAND="$1" "$HERE/vps-ops.sh" >"$TMP/out" 2>"$TMP/err"; }

for c in health status logs rehash-dry-run rehash-report; do
  run "$c" && [ -s "$VI_FAKE_LOG" ] && ok "allowed: $c" || bad "allowed: $c"
done

# deploy-info: read-only, reports origin/HEAD/backups from a throwaway git repo
ROOT="$TMP/root"; mkdir -p "$ROOT/backend"
git -C "$ROOT" init -q && git -C "$ROOT" -c user.name=t -c user.email=t@t commit -q --allow-empty -m "probe commit" \
  && git -C "$ROOT" remote add origin gitea-vibedinsight:marvin/VibedInsight.git
echo "-- SELECT 1;" > "$ROOT/backend/backup_predeploy_20260101_000000.sql"
VI_BACKEND_DIR="$ROOT/backend" run "deploy-info"; out="$(cat "$TMP/out")"
echo "$out" | grep -q "origin:  gitea-vibedinsight:marvin/VibedInsight.git" && echo "$out" | grep -q "probe commit" \
  && echo "$out" | grep -q "backup_predeploy_20260101_000000.sql" && [ ! -s "$VI_FAKE_LOG" ] \
  && ok "deploy-info reports origin, HEAD, backups (no docker call)" || bad "deploy-info output: $out"
run "rehash-dry-run" && grep -q -- "--dry-run" "$VI_FAKE_LOG" && ! grep -q -- "--apply" "$VI_FAKE_LOG" \
  && ok "rehash runs dry-run only" || bad "rehash runs dry-run only"

for c in "" "bash" "sh -c id" "health; id" 'health && id' 'health $(id)' '`id`' "health " " health" \
         "HEALTH" "logs --follow" "rehash --apply" "rehash-dry-run --apply" "cat /etc/passwd" \
         "docker ps" "../health" $'health\nid'; do
  run "$c"; rc=$?
  if [ $rc -ne 0 ] && [ ! -s "$VI_FAKE_LOG" ]; then ok "rejected: ${c:-<empty>}"; else bad "rejected: ${c:-<empty>} (rc=$rc)"; fi
done

unset SSH_ORIGINAL_COMMAND
: > "$VI_FAKE_LOG"; "$HERE/vps-ops.sh" >/dev/null 2>&1 </dev/null; rc=$?
[ $rc -ne 0 ] && [ ! -s "$VI_FAKE_LOG" ] && ok "rejected: unset command (interactive)" || bad "unset command"

echo "selftest: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
