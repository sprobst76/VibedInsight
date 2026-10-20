#!/bin/bash
# Run ON THE VPS as the deploy user, from the copied ops/ directory:
#   ./install-on-vps.sh                      install script + selftest
#   ./install-on-vps.sh ~/vi-ops.pub         ... and authorize the restricted key
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${VI_SCRIPTS_DIR:-/srv/vibedinsight/scripts}"
SCRIPT="$DEST/vps-ops.sh"

echo "[1/4] selftest (offline, fake docker)"
"$HERE/selftest.sh"

echo "[2/4] install $SCRIPT"
mkdir -p "$DEST"
install -m 0755 "$HERE/vps-ops.sh" "$SCRIPT"
ls -l "$SCRIPT"

if [ $# -lt 1 ]; then
  echo "[3/4] skipped (no public key given)"; echo "[4/4] skipped"; exit 0
fi

PUB="$1"
echo "[3/4] validate public key $PUB"
[ "$(grep -c . "$PUB")" -eq 1 ] || { echo "key file must contain exactly one line" >&2; exit 1; }
KEY="$(head -n1 "$PUB")"
case "$KEY" in
  ssh-ed25519\ AAAA*) ;;
  *) echo "expected an ssh-ed25519 public key" >&2; exit 1 ;;
esac
case "$KEY" in *\"*|*\\*) echo "key contains forbidden characters" >&2; exit 1 ;; esac
BLOB="$(echo "$KEY" | cut -d' ' -f2)"

echo "[4/4] authorize key (restrict + forced command)"
AK="$HOME/.ssh/authorized_keys"
mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"; touch "$AK"; chmod 600 "$AK"
if grep -qF "$BLOB" "$AK"; then
  echo "key already present in $AK, nothing changed"
else
  cp "$AK" "$AK.bak.$(date +%Y%m%d%H%M%S)"
  printf 'restrict,command="%s" %s vi-ops\n' "$SCRIPT" "$(echo "$KEY" | cut -d' ' -f1-2)" >> "$AK"
  echo "added. Existing keys untouched, backup: $AK.bak.*"
fi
