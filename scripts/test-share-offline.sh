#!/usr/bin/env bash
# Device test for the Android share path (online / offline queue / note).
# Prereqs: .dev APK installed (VI_DEV_SUFFIX=1 flutter build apk --release --split-per-abi),
# its server URL set to the dev backend (reachable from the phone), phone awake+unlocked
# (~/development/WorkflowAnalyser/scripts/adb-device-check.sh), dev stack up (./dev.sh up).
set -u
API="${API:-http://localhost:8100}"          # backend as seen from this machine
PKG="${PKG:-com.vibedinsight.app.dev}"
ACT="${ACT:-com.vibedinsight.vibedinsight.MainActivity}"
ADB="adb${ANDROID_SERIAL:+ -s $ANDROID_SERIAL}"
TOKEN="$(date +%s)$RANDOM"
FAIL=0

in_backend() { curl -s "$API/items?page_size=50" | grep -q "$1"; }
wait_backend() { # token timeout_s
  for _ in $(seq "$2"); do in_backend "$1" && return 0; sleep 1; done; return 1
}
share() { $ADB shell "am start -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT '$1' -n $PKG/$ACT" >/dev/null; }
focus() { $ADB shell dumpsys window | grep mCurrentFocus; }
check() { if [ "$1" = ok ]; then echo "PASS: $2"; else echo "FAIL: $2"; FAIL=1; fi; }
restore_net() { $ADB shell svc wifi enable; $ADB shell svc data enable; }
trap restore_net EXIT

$ADB shell input keyevent KEYCODE_WAKEUP
$ADB shell am force-stop "$PKG"

echo "== (a) online share =="
share "https://example.com/?share=a$TOKEN"
wait_backend "share=a$TOKEN" 10 && check ok "item in backend <10s" || check fail "item in backend <10s"
sleep 2
focus | grep -q "$PKG" && check fail "app closed after share" || check ok "app closed after share"

echo "== (b) offline share, then reconnect =="
$ADB shell am force-stop "$PKG"
$ADB shell svc wifi disable; $ADB shell svc data disable; sleep 4
share "https://example.com/?share=b$TOKEN"
sleep 8
in_backend "share=b$TOKEN" && check fail "not in backend while offline" || check ok "not in backend while offline"
focus | grep -q "$PKG" && check fail "app closed after offline share" || check ok "app closed after offline share"
restore_net
sleep 12   # wifi reconnect
$ADB shell am start -n "$PKG/$ACT" >/dev/null
wait_backend "share=b$TOKEN" 60 && check ok "queue flushed after reconnect+open" || check fail "queue flushed after reconnect+open"

echo "== (c) text without URL -> note =="
$ADB shell am force-stop "$PKG"
share "Notiztest-$TOKEN ohne URL"
wait_backend "Notiztest-$TOKEN" 10 && check ok "note in backend" || check fail "note in backend"

exit $FAIL
