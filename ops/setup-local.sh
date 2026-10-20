#!/bin/bash
# Run LOCALLY once: creates the dedicated key and the "vi-ops" ssh alias.
#   ./setup-local.sh <vps-user> [host]     (host defaults to the Tailscale name)
# Prints the public-key path to copy to the VPS.
set -eu
VPS_USER="${1:?usage: setup-local.sh <vps-user> [host]}"
HOST="${2:-halbwahrheit21-ts}"
KEY="$HOME/.ssh/vi-ops"
[ -f "$KEY" ] || ssh-keygen -t ed25519 -N "" -C vi-ops -f "$KEY" >/dev/null
CFG="$HOME/.ssh/config"; touch "$CFG"; chmod 600 "$CFG"
if ! grep -q '^Host vi-ops$' "$CFG"; then
  cat >> "$CFG" <<C

Host vi-ops
    HostName $HOST
    User $VPS_USER
    IdentityFile $KEY
    IdentitiesOnly yes
C
fi
# Existing alias: point it at the requested host (idempotent)
sed -i "/^Host vi-ops\$/,/^Host /{s|^\( *HostName \).*|\1$HOST|}" "$CFG"
echo "public key: $KEY.pub"
