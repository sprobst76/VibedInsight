#!/bin/bash
# Run LOCALLY after install: checks that the alias works AND that nothing else does.
# Uses ONE multiplexed connection (avoids firewall/fail2ban rate limits) and
# fails fast if the host is unreachable, so rejections can't be false positives.
set -u
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok   $1"; }
bad() { fail=$((fail+1)); echo "  FAIL $1"; }

CTL="$(mktemp -u /tmp/vi-ops-ctl.XXXXXX)"
trap 'ssh -O exit -o ControlPath="$CTL" vi-ops >/dev/null 2>&1' EXIT
SSHO=(-o BatchMode=yes -o ConnectTimeout=15 -o ControlMaster=auto -o ControlPath="$CTL" -o ControlPersist=60)
S() { ssh "${SSHO[@]}" vi-ops "$@"; }

# Preflight: a rejected command exits 126 with our message; anything else = no connection.
pre="$(S bogus-preflight 2>&1)"; rc=$?
if [ $rc -ne 126 ] || ! echo "$pre" | grep -q "not allowed"; then
  echo "ABORT: no working connection to vi-ops (rc=$rc):"; echo "$pre"
  echo "Check: ssh -v vi-ops health   |   ssh aiplatform@halbewahrheit21.de echo ok"
  exit 2
fi
ok "connected, forced command active (rc=126 for unknown command)"

out="$(S health 2>&1)"; echo "$out" | grep -q '"status"' && ok "health returns JSON" || bad "health: $out"
echo "$out" | grep -q '0\.7\.' && ok "version 0.7.x" || bad "version not 0.7.x: $out"
S status >/dev/null 2>&1 && ok "status" || bad "status"
S logs >"${CTL}.logs" 2>&1 && [ -s "${CTL}.logs" ] && ok "logs" || bad "logs"
S rehash-dry-run >/dev/null 2>&1 && ok "rehash-dry-run" || bad "rehash-dry-run"
S rehash-report 2>&1 | grep -q . && ok "rehash-report" || bad "rehash-report"
rm -f "${CTL}.logs"

for c in "id" "bash" "rehash --apply" "health; id" "cat /etc/passwd"; do
  S "$c" >/dev/null 2>&1; rc=$?
  [ $rc -eq 126 ] && ok "rejected: $c" || bad "must be rejected with 126, got rc=$rc: $c"
done
ssh -o BatchMode=yes -o ConnectTimeout=15 -o ControlPath=none -N -L 9999:localhost:22 vi-ops true >/dev/null 2>&1 \
  && bad "port forwarding must be blocked" || ok "port forwarding blocked (or connection refused)"

echo "verify-remote: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
