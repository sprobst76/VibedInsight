#!/bin/bash
# Run LOCALLY once: creates the dedicated key and the "vi-ops" ssh alias.
#   ./setup-local.sh <vps-user>
# Prints the public-key path to copy to the VPS.
set -eu
VPS_USER="${1:?usage: setup-local.sh <vps-user>}"
KEY="$HOME/.ssh/vi-ops"
[ -f "$KEY" ] || ssh-keygen -t ed25519 -N "" -C vi-ops -f "$KEY" >/dev/null
CFG="$HOME/.ssh/config"; touch "$CFG"; chmod 600 "$CFG"
if ! grep -q '^Host vi-ops$' "$CFG"; then
  cat >> "$CFG" <<C

Host vi-ops
    HostName halbewahrheit21.de
    User $VPS_USER
    IdentityFile $KEY
    IdentitiesOnly yes
C
fi
echo "public key: $KEY.pub"
