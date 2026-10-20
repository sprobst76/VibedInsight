#!/bin/bash
# Run LOCALLY after install: checks that the alias works AND that nothing else does.
set -u
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok   $1"; }
bad() { fail=$((fail+1)); echo "  FAIL $1"; }
S() { ssh -o BatchMode=yes -o ConnectTimeout=10 vi-ops "$@"; }

out="$(S health 2>&1)"; echo "$out" | grep -q '"status"' && ok "health returns JSON" || bad "health: $out"
echo "$out" | grep -q '0\.7\.' && ok "version 0.7.x" || bad "version not 0.7.x: $out"
S status >/dev/null 2>&1 && ok "status" || bad "status"
S logs 2>&1 | grep -q . && ok "logs" || bad "logs"
S rehash-dry-run >/dev/null 2>&1 && ok "rehash-dry-run" || bad "rehash-dry-run"
S rehash-report 2>&1 | grep -q . && ok "rehash-report" || bad "rehash-report"

for c in "id" "bash" "rehash --apply" "health; id" "cat /etc/passwd"; do
  S "$c" >/dev/null 2>&1 && bad "must be rejected: $c" || ok "rejected: $c"
done
S -N -L 9999:localhost:22 true >/dev/null 2>&1 && bad "port forwarding must be blocked" || ok "port forwarding blocked"
scp -q -o BatchMode=yes vi-ops:/etc/passwd /dev/null >/dev/null 2>&1 && bad "scp must be blocked" || ok "scp blocked"

echo "verify-remote: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
