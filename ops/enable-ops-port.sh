#!/bin/bash
# Run ON THE VPS with sudo. Tailscale SSH intercepts port 22 on the tailnet and
# ignores authorized_keys (so no forced command). This adds a second sshd port,
# bound to the Tailscale IP only, where plain sshd + authorized_keys apply.
# Port 22 and your existing login are not touched.
set -eu
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
PORT="${VI_OPS_PORT:-2223}"
TSIP="$(tailscale ip -4 | head -n1)"
[ -n "$TSIP" ] || { echo "no Tailscale IPv4 found" >&2; exit 1; }
echo "Tailscale IP: $TSIP, new port: $PORT"

if systemctl is-active --quiet ssh.socket 2>/dev/null; then
  echo "mode: systemd socket activation (ssh.socket)"
  mkdir -p /etc/systemd/system/ssh.socket.d
  cat > /etc/systemd/system/ssh.socket.d/vi-ops.conf <<C
[Socket]
ListenStream=$TSIP:$PORT
FreeBind=true
C
  systemctl daemon-reload
  systemctl restart ssh.socket
else
  echo "mode: plain sshd service"
  CONF=/etc/ssh/sshd_config.d/90-vi-ops.conf
  [ -d /etc/ssh/sshd_config.d ] || { echo "no sshd_config.d; edit sshd_config by hand" >&2; exit 1; }
  cat > "$CONF" <<C
Port 22
ListenAddress 0.0.0.0
ListenAddress ::
ListenAddress $TSIP:$PORT
C
  if ! sshd -t; then rm -f "$CONF"; echo "sshd config invalid, change reverted" >&2; exit 1; fi
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
fi

sleep 1
if ss -ltn | grep -q "$TSIP:$PORT"; then
  echo "OK: sshd listens on $TSIP:$PORT"
else
  echo "FAIL: nothing listens on $TSIP:$PORT" >&2; exit 1
fi
