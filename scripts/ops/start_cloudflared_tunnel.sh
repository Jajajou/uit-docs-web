#!/usr/bin/env bash
# scripts/ops/start_cloudflared_tunnel.sh
#
# Expose the LangGraph upstream (which lives inside the Tailscale tailnet at
# https://jajajou-bro.tail402a6.ts.net) over a public HTTPS endpoint so that
# Render — which cannot join the tailnet — can call it.
#
# This uses Cloudflare's "trycloudflare" quick-tunnel: no Cloudflare account
# or domain required, the tunnel allocates a random https://*.trycloudflare.com
# URL, and the URL changes every time the tunnel restarts. That is fine for
# Phase 0/1 staging per user direction.
#
# REQUIREMENTS:
#   * cloudflared installed on PATH. On Windows:
#       winget install --id Cloudflare.cloudflared
#     On macOS:
#       brew install cloudflared
#     On Linux (Debian/Ubuntu):
#       curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
#       sudo dpkg -i /tmp/cloudflared.deb
#   * The host running this script MUST be joined to the Tailscale tailnet
#     where `https://jajajou-bro.tail402a6.ts.net` resolves. Verify with:
#       tailscale status
#       curl -I https://jajajou-bro.tail402a6.ts.net/ok
#
# USAGE:
#   bash scripts/ops/start_cloudflared_tunnel.sh
#
# ON OUTPUT:
#   The tunnel prints a line like
#     INF |  https://something-random.trycloudflare.com
#   Copy that URL and paste it into Render's environment variables for
#   uit-docs-backend:
#     LANGGRAPH_URL          = https://something-random.trycloudflare.com
#     LANGGRAPH_PUBLIC_URL   = https://something-random.trycloudflare.com
#     LANGGRAPH_UPSTREAM_URL = https://something-random.trycloudflare.com
#
# Then click "Manual Deploy -> Clear build cache & deploy" so the new env
# vars take effect.
#
# WHEN THE TUNNEL CRASHES OR YOU REBOOT:
#   The trycloudflare URL is regenerated on the next run. Re-paste the new
#   URL into Render and redeploy. To avoid this, register a free Cloudflare
#   account, claim a domain (or use cloudflare-managed *.cloudflare.com via
#   `cloudflared tunnel create` + `cloudflared tunnel route dns`), and edit
#   this script to call `cloudflared tunnel run <named-tunnel>` instead.

set -euo pipefail

UPSTREAM="${UPSTREAM_URL:-https://jajajou-bro.tail402a6.ts.net}"

if ! command -v cloudflared >/dev/null 2>&1; then
    echo "error: cloudflared is not on PATH; install it first (see header)." >&2
    exit 1
fi

# Sanity probe: the host MUST be on the tailnet so cloudflared can reach
# the LangGraph upstream when it forwards traffic.
if ! curl --max-time 5 -fsS "${UPSTREAM%/}/ok" >/dev/null 2>&1; then
    cat >&2 <<EOF
warning: ${UPSTREAM}/ok did not return 2xx within 5 seconds.
This usually means:
  1. The Tailscale daemon is down on this host. Run: tailscale up
  2. The LangGraph service inside the tailnet is offline.
  3. The hostname has changed (rebuilt host -> new tail*.ts.net name).

The tunnel will still start, but Render -> backend -> LangGraph requests
will fail with HTTP 5xx until the upstream is reachable from THIS host.
Press Ctrl-C now to abort, or any key to continue.
EOF
    read -r _key
fi

echo "Starting Cloudflare quick-tunnel for ${UPSTREAM}..."
echo "Look for the trycloudflare.com URL in the output below; copy it into"
echo "the LANGGRAPH_URL / LANGGRAPH_PUBLIC_URL / LANGGRAPH_UPSTREAM_URL env"
echo "vars on Render and redeploy uit-docs-backend."
echo

# `--no-tls-verify` lets cloudflared accept the Tailscale upstream's
# tailnet-issued certificate. Tailscale's HTTPS endpoints use a tailnet CA
# that public CAs do not trust; this flag is safe because the TCP path is
# already inside the encrypted tailnet.
exec cloudflared tunnel \
    --url "${UPSTREAM}" \
    --no-tls-verify \
    --loglevel info
