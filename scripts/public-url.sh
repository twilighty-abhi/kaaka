#!/usr/bin/env bash
# Gives the Kaaka dashboard a public https URL with a Cloudflare quick tunnel, so the location link
# in the caller's reply SMS works from any phone browser.
#
# Usage: scripts/public-url.sh            (HTTP_PORT=8080 by default)
# Keeps running while the tunnel is up; press Ctrl-C to close it. The URL changes on every run.
#
# Before exposing the dashboard, set an admin token: the server refuses to start with a public URL
# without one, because callers' numbers and locations would otherwise be readable by anyone.
set -euo pipefail

PORT="${HTTP_PORT:-8080}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Install it with:"
  echo "  brew install cloudflared"
  exit 1
fi
if ! curl -s -m 3 -o /dev/null "http://127.0.0.1:${PORT}/api/status"; then
  echo "Nothing answers on http://127.0.0.1:${PORT}. Start the dashboard first:"
  echo "  .venv-mac/bin/python server/server.py"
  exit 1
fi

LOG="$(mktemp)"
cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate > "$LOG" 2>&1 &
TUNNEL=$!
trap 'kill $TUNNEL 2>/dev/null || true; rm -f "$LOG"' EXIT

echo "Opening tunnel to http://localhost:${PORT} ..."
URL=""
for _ in $(seq 1 30); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "Tunnel did not report a URL within 30 s. cloudflared output:"
  tail -20 "$LOG"
  exit 1
fi

TOKEN="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)"
cat <<EOF

Public URL: $URL

Next steps:
1. Restart the dashboard with the public URL and an admin token (pick your own or use this one):
     KAAKA_PUBLIC_URL=$URL KAAKA_ADMIN_TOKEN=$TOKEN .venv-mac/bin/python server/server.py
2. In Kaaka Call on the gateway phone: [config] -> dashboard token = the same token -> save.
   The phone picks up the public URL from the dashboard's heartbeat reply within a minute;
   leave "public link url" empty (or set it to $URL to pin it).
3. Open the dashboard yourself at $URL/admin?token=$TOKEN
4. Call the Kaaka number: the reply SMS now ends with "Share your location: $URL/l/<token>".

The tunnel stays open while this script runs. Ctrl-C closes it (the URL stops working).
EOF
wait "$TUNNEL"
