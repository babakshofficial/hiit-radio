#!/usr/bin/env bash
# Stop and remove Cloudflare tunnel / DoH stub systemd units from this machine.
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

systemctl disable --now cloudflared doh-dns-stub 2>/dev/null || true
systemctl disable --now dnscrypt-proxy dnscrypt-proxy.socket 2>/dev/null || true

rm -rf /etc/systemd/system/cloudflared.service.d
rm -f /etc/systemd/system/doh-dns-stub.service
rm -f /etc/systemd/resolved.conf.d/local-doh.conf
rm -f /etc/systemd/resolved.conf.d/cloudflare-dot.conf

systemctl daemon-reload
systemctl reset-failed cloudflared doh-dns-stub 2>/dev/null || true
systemctl restart systemd-resolved 2>/dev/null || true

if command -v cloudflared >/dev/null 2>&1 || [[ -x /home/babak/.local/bin/cloudflared ]]; then
  echo "To remove the cloudflared systemd unit and token:"
  echo "  cloudflared service uninstall   # or: ~/.local/bin/cloudflared service uninstall"
fi

echo "Done. cloudflared and doh-dns-stub are stopped/disabled."
